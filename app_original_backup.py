import os
import logging
import json
from datetime import datetime
import pandas as pd
import mlflow
from mlflow.tracking import MlflowClient
from flask import Flask, request
from flask_restx import Api, Resource, fields
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from MLModel import CreditScoringModel # Átnevezett osztály
# from constants import COLUMN_NAMES # Győződj meg róla, hogy ez a pénzügyi oszlopokat tartalmazza!

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MLFLOW_TRACKING_URI = "http://127.0.0.1:5102"
EXPERIMENT_NAME = "credit_scoring_shadow_experiment"

app = Flask(__name__)
api = Api(app, version='2.0', title='Credit Scoring API', description='Pénzügyi kockázatelemzés és NLP alapú Bias detektálás.')

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
client = MlflowClient()
if not mlflow.get_experiment_by_name(EXPERIMENT_NAME):
    mlflow.create_experiment(EXPERIMENT_NAME)
mlflow.set_experiment(EXPERIMENT_NAME)

obj_mlmodel = CreditScoringModel(client=client)

ns = api.namespace('scoring', description='Hitelminősítési Műveletek')

# --- PÉNZÜGYI INPUT MODELL DEFINÍCIÓ ---
credit_input_fields = {
    'NetSales': fields.Float(example=50000000),
    'Operating Margin': fields.Float(example=12.5),
    'Current Ratio': fields.Float(example=1.5),
    'DebtToEquityRatio': fields.Float(example=2.1),
    'Return on Assets (ROA)': fields.Float(example=5.4),
    'LatePaymentCount': fields.Integer(example=0),
    'Industry_code': fields.String(example="Építőipar"),
    'legal_entity_type': fields.String(example="Kft."),
    'description': fields.String(example="Stabilan működő cég, növekvő árbevétellel.", description="Kockázati elemzői megjegyzés")
}

predict_input_model = api.model('ScoringInput', {
    'application_data': fields.Nested(api.model('ApplicationData', credit_input_fields), required=True)
})

file_upload_parser = api.parser()
file_upload_parser.add_argument('file', location='files', type=FileStorage, required=True, help='Tanító adatbázis (CSV)')

@ns.route('/train')
class Train(Resource):
    @ns.expect(file_upload_parser)
    def post(self):
        args = file_upload_parser.parse_args()
        uploaded_file = args['file']
        
        temp_path = f"temp_{secure_filename(uploaded_file.filename)}"
        uploaded_file.save(temp_path)
        
        try:
            with mlflow.start_run(run_name=f"credit_train_{datetime.now().strftime('%Y%m%d')}") as run:
                df = pd.read_csv(temp_path)
                
                # Célváltozó kezelés (Default = 1)
                if 'target' in df.columns and 'target_binary' not in df.columns:
                    df['target_binary'] = (df['target'] > 0).astype(int)

                # TANÍTÁS + RÉSZLETES METRIKÁK
                results = obj_mlmodel.train_shadow_system(df)
                
                champ_metrics = results['champion']
                chall_metrics = results['challenger']
                
                # Metrikák logolása MLflow-ba
                for metric, value in champ_metrics.items():
                    mlflow.log_metric(f"champion_{metric}", value)
                
                for metric, value in chall_metrics.items():
                    mlflow.log_metric(f"challenger_{metric}", value)
                
                # Model Registry
                model_uri = f"runs:/{run.info.run_id}/champion_model"
                mv = mlflow.register_model(model_uri, "Credit_Scoring_Champion")
                client.set_registered_model_alias("Credit_Scoring_Champion", "latest_training", mv.version)

            return {
                'message': 'Credit Scoring modell betanítva.',
                'metrics': results # Visszaadjuk a teljes struktúrát (F1, Recall, stb.)
            }, 200

        except Exception as e:
            logger.error(f"Hiba: {e}", exc_info=True)
            return {'error': str(e)}, 500
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)

@ns.route('/predict')
class Predict(Resource):
    @api.expect(predict_input_model)
    def post(self):
        try:
            data = request.get_json()
            app_data = data.get('application_data')
            
            # INFERENCE
            result = obj_mlmodel.predict_shadow_mode(app_data)
            
            # Logolás
            with mlflow.start_run(run_name="scoring_request"):
                mlflow.log_param("sentiment_score", result['shadow_meta']['sentiment_score'])
                mlflow.log_metric("prob_default", result['pd_score'])
                mlflow.log_dict(result, "scoring_result.json")

            return {
                'status': 'success',
                'prediction': "DEFAULT (Elutasít)" if result['prediction'] == 1 else "NON-DEFAULT (Elfogad)",
                'probability_of_default': result['pd_score'],
                'metrics_info': "Modell F1 és ROC-AUC alapján dönt.",
                'shadow_metadata': result['shadow_meta']
            }, 200

        except Exception as e:
            logger.error(f"Scoring hiba: {e}", exc_info=True)
            return {'error': str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)