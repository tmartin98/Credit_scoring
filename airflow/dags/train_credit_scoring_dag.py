import time
import requests
import logging
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.email import EmailOperator
from airflow.models import TaskInstance
import mlflow
from mlflow.tracking import MlflowClient

# Konfiguráció
MLFLOW_URI = "http://mlflow:5102"
API_TRAIN_ENDPOINT = "http://api:8080/scoring/train"
API_STATS_ENDPOINT = "http://api:8080/api/predictions/stats"
MODEL_NAME = "Credit_Scoring_Champion"
CSV_FILE_PATH = "/opt/airflow/data/credit_data_raw.csv"
NOTIFICATION_EMAIL = "turcsanyi.martin98@gmail.com"

logger = logging.getLogger("airflow.task")
mlflow.set_tracking_uri(MLFLOW_URI)
client = MlflowClient()

def train_and_compare(**kwargs):
    """
    Meghívja a Credit Scoring Train API-t.
    Összehasonlítja az új modellt a régivel F1-Score és ROC-AUC alapján.
    """
    ti = kwargs['ti']
    
    # 1. API Hívás
    with open(CSV_FILE_PATH, 'rb') as f:
        files = {'file': ('data.csv', f)}
        resp = requests.post(API_TRAIN_ENDPOINT, files=files, timeout=600)
    
    if resp.status_code != 200:
        raise Exception(f"API Hiba: {resp.text}")
    
    # JSON válasz feldolgozása (Részletes metrikák!)
    data = resp.json()
    metrics = data.get('metrics', {})
    
    # Új modell (Champion) metrikái
    new_champ = metrics.get('champion', {})
    new_f1 = new_champ.get('f1_score', 0.0)
    new_auc = new_champ.get('roc_auc', 0.0)
    
    logger.info(f"Új Modell - F1: {new_f1:.4f}, AUC: {new_auc:.4f}")
    
    # Adatok mentése XCom-ba
    ti.xcom_push(key='new_metrics', value=new_champ)
    ti.xcom_push(key='challenger_metrics', value=metrics.get('challenger', {}))

    # 2. Jelenlegi Éles Modell (Production) lekérése
    current_f1 = 0.0
    try:
        alias = client.get_model_version_by_alias(MODEL_NAME, "Production")
        run = mlflow.get_run(alias.run_id)
        current_f1 = run.data.metrics.get("champion_f1_score", 0.0)
        logger.info(f"Production Modell - F1: {current_f1:.4f}")
    except:
        logger.info("Nincs Production modell, az új nyer.")

    ti.xcom_push(key='current_f1', value=current_f1)

    # 3. Döntés (F1 Score alapján)
    if new_f1 >= current_f1:
        return 'promote_to_production'
    return 'send_alert'

def promote_production(**kwargs):
    latest = client.get_model_version_by_alias(MODEL_NAME, "latest_training")
    client.set_registered_model_alias(MODEL_NAME, "Production", latest.version)
    logger.info(f"Credit Scoring v{latest.version} előléptetve Production-be.")

# DAG
default_args = {'owner': 'risk_team', 'retries': 1, 'retry_delay': timedelta(minutes=5)}

with DAG(
    dag_id="credit_scoring_automl_pipeline",
    default_args=default_args,
    schedule_interval="0 2 * * *",
    start_date=datetime(2023, 1, 1),
    catchup=False
) as dag:

    t1 = BranchPythonOperator(
        task_id='train_and_compare',
        python_callable=train_and_compare,
        provide_context=True
    )

    t2 = PythonOperator(
        task_id='promote_to_production',
        python_callable=promote_production,
        provide_context=True
    )

    # Részletes Email sablon táblázattal
    email_content = """
    <h3>Credit Scoring Modell Riport 📊</h3>
    <table border="1" cellpadding="5">
        <tr>
            <th>Metrika</th>
            <th>Új Champion (XGB)</th>
            <th>Új Challenger (LGBM)</th>
            <th>Régi Production</th>
        </tr>
        <tr>
            <td><b>F1-Score</b></td>
            <td>{{ ti.xcom_pull(task_ids='train_and_compare', key='new_metrics')['f1_score'] | round(4) }}</td>
            <td>{{ ti.xcom_pull(task_ids='train_and_compare', key='challenger_metrics')['f1_score'] | round(4) }}</td>
            <td>{{ ti.xcom_pull(task_ids='train_and_compare', key='current_f1') | round(4) }}</td>
        </tr>
        <tr>
            <td><b>ROC-AUC</b></td>
            <td>{{ ti.xcom_pull(task_ids='train_and_compare', key='new_metrics')['roc_auc'] | round(4) }}</td>
            <td>{{ ti.xcom_pull(task_ids='train_and_compare', key='challenger_metrics')['roc_auc'] | round(4) }}</td>
            <td>-</td>
        </tr>
        <tr>
            <td><b>Recall</b></td>
            <td>{{ ti.xcom_pull(task_ids='train_and_compare', key='new_metrics')['recall'] | round(4) }}</td>
            <td>{{ ti.xcom_pull(task_ids='train_and_compare', key='challenger_metrics')['recall'] | round(4) }}</td>
            <td>-</td>
        </tr>
    </table>
    <p><i>Megjegyzés: Ha az F1-Score csökkent, a modell nem került élesítésre.</i></p>
    """
    
    t3 = EmailOperator(
        task_id='send_alert',
        to=NOTIFICATION_EMAIL,
        subject='[Risk] Credit Scoring Model Update',
        html_content=email_content
    )

    t1 >> [t2, t3]