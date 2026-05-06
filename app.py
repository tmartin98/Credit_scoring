"""
Credit Scoring API - Flask REST API MLflow + PostgreSQL integrációval.
Végpontok:
  POST /scoring/train     - Modell betanítása CSV fájlból
  POST /scoring/predict   - Predikció ügyféladatokra
  POST /api/customers     - Ügyfél rögzítése
  GET  /api/customers     - Ügyfelek listája
  GET  /api/customers/<id>         - Ügyfél adatok
  GET  /api/customers/<id>/predictions - Ügyfél predikciói
  GET  /api/predictions   - Predikciók listája
  GET  /api/predictions/stats      - Statisztikák
  GET  /health            - Health check
  /admin/*                - Admin felület
"""
import os
import logging
import json
from datetime import datetime

import requests
import pandas as pd
import mlflow
from mlflow.tracking import MlflowClient
from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from MLModel import CreditScoringModel
from database import init_db, check_db_connection, SessionLocal
from database_models import AdminUser
import db_service
from admin_routes import admin_bp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Config ---
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5102")
EXPERIMENT_NAME = "credit_scoring_shadow_experiment"
SECRET_KEY = os.getenv("SECRET_KEY", "credit_scoring_secret_key_2024")
AIRFLOW_BASE_URL = os.getenv("AIRFLOW_BASE_URL", "http://airflow_webserver:8080")
AIRFLOW_USER = os.getenv("AIRFLOW_USER", "admin")
AIRFLOW_PASSWORD = os.getenv("AIRFLOW_PASSWORD", "admin")
AIRFLOW_DAG_ID = "credit_scoring_automl_pipeline"

# --- Flask App ---
app = Flask(__name__)
app.secret_key = SECRET_KEY

# --- MLflow (lazy init - tolerálja, ha MLflow induláskor még nem elérhető) ---
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
client = None
try:
    client = MlflowClient()
    if not mlflow.get_experiment_by_name(EXPERIMENT_NAME):
        mlflow.create_experiment(EXPERIMENT_NAME)
    mlflow.set_experiment(EXPERIMENT_NAME)
    logger.info(f"✅ MLflow kapcsolat: {MLFLOW_TRACKING_URI}")
except Exception as e:
    logger.warning(f"⚠️  MLflow nem elérhető induláskor (folytatás DB-vel): {e}")


def _ensure_mlflow_experiment():
    """Elvégzi az MLflow kísérlet inicializációt, ha még nem sikerült."""
    global client
    if client is None:
        try:
            client = MlflowClient()
            if not mlflow.get_experiment_by_name(EXPERIMENT_NAME):
                mlflow.create_experiment(EXPERIMENT_NAME)
            mlflow.set_experiment(EXPERIMENT_NAME)
        except Exception as e:
            logger.warning(f"MLflow még nem elérhető: {e}")

# --- ML Model ---
obj_mlmodel = CreditScoringModel(client=client)

# --- Admin Blueprint ---
app.register_blueprint(admin_bp)

# --- REST API ---
api = Api(
    app,
    version="2.0",
    title="Credit Scoring API",
    description="Pénzügyi kockázatelemzés, Shadow System, NLP Bias detektálás.",
    doc="/swagger",
)

# Namespaces
ns_scoring = api.namespace("scoring", description="Hitelminősítési műveletek")
ns_customers = api.namespace("api/customers", description="Ügyfélkezelés")
ns_predictions = api.namespace("api/predictions", description="Predikciók")

# --- Models ---
credit_input_fields = {
    "NetSales": fields.Float(example=50000000),
    "Operating Margin": fields.Float(example=12.5),
    "Current Ratio": fields.Float(example=1.5),
    "DebtToEquityRatio": fields.Float(example=2.1),
    "Return on Assets (ROA)": fields.Float(example=5.4),
    "LatePaymentCount": fields.Integer(example=0),
    "Industry_code": fields.String(example="Építőipar"),
    "legal_entity_type": fields.String(example="Kft."),
    "description": fields.String(example="Stabil, növekvő cég."),
}

predict_input_model = api.model("ScoringInput", {
    "application_data": fields.Nested(
        api.model("ApplicationData", credit_input_fields), required=True
    ),
    "customer_id": fields.String(description="Opcionális ügyfél UUID a DB-ből", example=None),
})

customer_model = api.model("CustomerCreate", {
    "name": fields.String(required=True, example="Példa Kft."),
    "email": fields.String(example="info@pelda.hu"),
    "Industry_code": fields.String(example="Ipar"),
    "legal_entity_type": fields.String(example="Kft."),
    "NetSales": fields.Float(example=10000000),
    "Operating Margin": fields.Float(example=8.0),
    "Current Ratio": fields.Float(example=1.2),
    "DebtToEquityRatio": fields.Float(example=1.5),
    "Return on Assets (ROA)": fields.Float(example=4.0),
    "LatePaymentCount": fields.Integer(example=0),
    "description": fields.String(example="Stabil cég."),
})

file_upload_parser = api.parser()
file_upload_parser.add_argument("file", location="files", type=FileStorage, required=True, help="Tanító adatbázis (CSV)")

# -------------------------------------------------------
# SCORING ENDPOINTS
# -------------------------------------------------------

@ns_scoring.route("/train")
class Train(Resource):
    @ns_scoring.expect(file_upload_parser)
    def post(self):
        """Modell betanítása CSV fájlból. Eredmények MLflow-ba és DB-be mentve."""
        _ensure_mlflow_experiment()
        args = file_upload_parser.parse_args()
        uploaded_file = args["file"]
        temp_path = f"temp_{secure_filename(uploaded_file.filename)}"
        uploaded_file.save(temp_path)

        try:
            with mlflow.start_run(run_name=f"credit_train_{datetime.now().strftime('%Y%m%d_%H%M%S')}") as run:
                df = pd.read_csv(temp_path)
                # Target oszlop normalizálása
                if "target_binary" not in df.columns:
                    if "target" in df.columns:
                        df["target_binary"] = (df["target"] > 0).astype(int)
                    elif "has_prior_default" in df.columns:
                        df["target_binary"] = df["has_prior_default"].astype(int)
                    elif "loan_grade" in df.columns:
                        # A/B/C = jó (0), D/E/F/G = default (1)
                        bad_grades = {"D", "E", "F", "G"}
                        df["target_binary"] = df["loan_grade"].apply(
                            lambda g: 1 if str(g).strip().upper() in bad_grades else 0
                        )
                    else:
                        return {"error": "A CSV-ből hiányzik a target oszlop (target_binary / target / has_prior_default / loan_grade)."}, 400

                results = obj_mlmodel.train_shadow_system(df)

                # MLflow metrikák
                for metric, value in results["champion"].items():
                    mlflow.log_metric(f"champion_{metric}", value)
                for metric, value in results["challenger"].items():
                    mlflow.log_metric(f"challenger_{metric}", value)

                # Model Registry
                model_uri = f"runs:/{run.info.run_id}/champion_model"
                try:
                    mv = mlflow.register_model(model_uri, "Credit_Scoring_Champion")
                    client.set_registered_model_alias("Credit_Scoring_Champion", "latest_training", mv.version)
                    version_str = str(mv.version)
                except Exception as e:
                    logger.warning(f"Model registry hiba (folytatás): {e}")
                    version_str = "unknown"

                # DB mentés
                db = SessionLocal()
                try:
                    db_service.save_model_version(db, {
                        "model_name": "Credit_Scoring_Champion",
                        "version": version_str,
                        "mlflow_run_id": run.info.run_id,
                        "champion": results["champion"],
                        "challenger": results["challenger"],
                    })
                finally:
                    db.close()

            return {
                "message": "Credit Scoring modell sikeresen betanítva.",
                "run_id": run.info.run_id,
                "metrics": results,
            }, 200

        except Exception as e:
            logger.error(f"Train hiba: {e}", exc_info=True)
            return {"error": str(e)}, 500
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


@ns_scoring.route("/trigger-training")
class TriggerTraining(Resource):
    def post(self):
        """Elindítja az Airflow credit_scoring_automl_pipeline DAG-ot.
        A tanítás eredménye látszik: Airflow UI-ban, MLflow-ban és az Admin UI-ban is."""
        dag_run_id = f"manual__{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        url = f"{AIRFLOW_BASE_URL}/api/v1/dags/{AIRFLOW_DAG_ID}/dagRuns"
        try:
            resp = requests.post(
                url,
                json={"dag_run_id": dag_run_id, "conf": {}},
                auth=(AIRFLOW_USER, AIRFLOW_PASSWORD),
                timeout=15,
            )
            if resp.status_code in (200, 409):
                data = resp.json()
                return {
                    "message": "✅ Airflow DAG tanítás sikeresen elindítva.",
                    "dag_run_id": data.get("dag_run_id", dag_run_id),
                    "state": data.get("state", "queued"),
                    "links": {
                        "airflow_dag": "http://localhost:8793/dags/credit_scoring_automl_pipeline/grid",
                        "mlflow": "http://localhost:5102",
                        "admin_model_versions": "http://localhost:8080/admin/model-versions",
                    },
                    "note": "A status endpoint segítségével követhető a futás állapota.",
                }, 200
            return {"error": f"Airflow hiba: {resp.status_code} – {resp.text}"}, 502
        except requests.exceptions.ConnectionError:
            return {"error": f"Airflow nem elérhető: {AIRFLOW_BASE_URL}"}, 503
        except Exception as e:
            logger.error(f"Trigger training hiba: {e}", exc_info=True)
            return {"error": str(e)}, 500


@ns_scoring.route("/training-status/<string:dag_run_id>")
class TrainingStatus(Resource):
    def get(self, dag_run_id):
        """Airflow DAG futás állapotának lekérése a dag_run_id alapján."""
        url = f"{AIRFLOW_BASE_URL}/api/v1/dags/{AIRFLOW_DAG_ID}/dagRuns/{dag_run_id}"
        try:
            resp = requests.get(url, auth=(AIRFLOW_USER, AIRFLOW_PASSWORD), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "dag_run_id": dag_run_id,
                    "state": data.get("state"),
                    "start_date": data.get("start_date"),
                    "end_date": data.get("end_date"),
                    "note": data.get("note", ""),
                }, 200
            return {"error": f"DAG futás nem található: {resp.status_code}"}, 404
        except requests.exceptions.ConnectionError:
            return {"error": f"Airflow nem elérhető: {AIRFLOW_BASE_URL}"}, 503
        except Exception as e:
            return {"error": str(e)}, 500


@ns_scoring.route("/predict")
class Predict(Resource):
    @api.expect(predict_input_model)
    def post(self):
        """Hitelminősítési predikció. Eredmény DB-be és MLflow-ba mentve."""
        _ensure_mlflow_experiment()
        try:
            data = request.get_json()
            app_data = data.get("application_data", {})
            customer_id = data.get("customer_id")

            result = obj_mlmodel.predict_shadow_mode(app_data)

            # MLflow logolás
            run_id = None
            try:
                with mlflow.start_run(run_name="scoring_request") as run:
                    mlflow.log_param("sentiment_score", result["shadow_meta"]["sentiment_score"])
                    mlflow.log_metric("prob_default", result["pd_score"])
                    mlflow.log_dict(result, "scoring_result.json")
                    run_id = run.info.run_id
            except Exception as e:
                logger.warning(f"MLflow logolás sikertelen: {e}")

            # DB mentés
            db = SessionLocal()
            try:
                # Aktuális production modell lekérése
                prod = db_service.get_production_model(db)
                model_ver = prod.version if prod else None

                pred_record = db_service.save_prediction(
                    db,
                    prediction_result=result,
                    input_data=app_data,
                    customer_id=customer_id,
                    model_version=model_ver,
                    mlflow_run_id=run_id,
                )
                prediction_id = str(pred_record.id)
            finally:
                db.close()

            return {
                "status": "success",
                "prediction_id": prediction_id,
                "prediction": "DEFAULT (Elutasít)" if result["prediction"] == 1 else "NON-DEFAULT (Elfogad)",
                "probability_of_default": result["pd_score"],
                "shadow_metadata": result["shadow_meta"],
            }, 200

        except Exception as e:
            logger.error(f"Predict hiba: {e}", exc_info=True)
            return {"error": str(e)}, 500


# -------------------------------------------------------
# CUSTOMER ENDPOINTS
# -------------------------------------------------------

@ns_customers.route("")
class CustomerList(Resource):
    @api.expect(customer_model)
    def post(self):
        """Új ügyfél rögzítése."""
        data = request.get_json()
        db = SessionLocal()
        try:
            customer = db_service.create_customer(db, data)
            return {"message": "Ügyfél rögzítve.", "customer": customer.to_dict()}, 201
        except Exception as e:
            logger.error(f"Customer create hiba: {e}", exc_info=True)
            return {"error": str(e)}, 500
        finally:
            db.close()

    def get(self):
        """Ügyfelek listája."""
        skip = request.args.get("skip", 0, type=int)
        limit = request.args.get("limit", 100, type=int)
        db = SessionLocal()
        try:
            customers = db_service.get_all_customers(db, skip=skip, limit=limit)
            return {"customers": [c.to_dict() for c in customers], "total": len(customers)}, 200
        finally:
            db.close()


@ns_customers.route("/<string:customer_id>")
class CustomerDetail(Resource):
    def get(self, customer_id):
        """Ügyfél adatok lekérése."""
        db = SessionLocal()
        try:
            customer = db_service.get_customer(db, customer_id)
            if not customer:
                return {"error": "Ügyfél nem található."}, 404
            return customer.to_dict(), 200
        finally:
            db.close()

    def put(self, customer_id):
        """Ügyfél adatok módosítása."""
        data = request.get_json()
        db = SessionLocal()
        try:
            customer = db_service.update_customer(db, customer_id, data)
            if not customer:
                return {"error": "Ügyfél nem található."}, 404
            return {"message": "Ügyfél frissítve.", "customer": customer.to_dict()}, 200
        finally:
            db.close()

    def delete(self, customer_id):
        """Ügyfél törlése."""
        db = SessionLocal()
        try:
            success = db_service.delete_customer(db, customer_id)
            if not success:
                return {"error": "Ügyfél nem található."}, 404
            return {"message": "Ügyfél törölve."}, 200
        finally:
            db.close()


@ns_customers.route("/<string:customer_id>/predictions")
class CustomerPredictions(Resource):
    def get(self, customer_id):
        """Ügyfél predikciós előzményei."""
        db = SessionLocal()
        try:
            preds = db_service.get_predictions_for_customer(db, customer_id)
            return {"predictions": [p.to_dict() for p in preds], "total": len(preds)}, 200
        finally:
            db.close()


# -------------------------------------------------------
# PREDICTIONS ENDPOINTS
# -------------------------------------------------------

@ns_predictions.route("")
class PredictionList(Resource):
    def get(self):
        """Legutóbbi predikciók listája."""
        limit = request.args.get("limit", 100, type=int)
        db = SessionLocal()
        try:
            preds = db_service.get_recent_predictions(db, limit=limit)
            return {"predictions": [p.to_dict() for p in preds], "total": len(preds)}, 200
        finally:
            db.close()


@ns_predictions.route("/stats")
class PredictionStats(Resource):
    def get(self):
        """Predikciós statisztikák (default arány, bias detektálás stb.)."""
        db = SessionLocal()
        try:
            return db_service.get_predictions_stats(db), 200
        finally:
            db.close()


# -------------------------------------------------------
# HEALTH CHECK
# -------------------------------------------------------

@app.route("/health")
def health():
    db_ok = check_db_connection()
    return jsonify({
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "mlflow_uri": MLFLOW_TRACKING_URI,
        "timestamp": datetime.utcnow().isoformat(),
    }), 200 if db_ok else 503


# -------------------------------------------------------
# STARTUP
# -------------------------------------------------------

def _bootstrap():
    """Adatbázis inicializáció és alapértelmezett admin felhasználó."""
    init_db()
    db = SessionLocal()
    try:
        existing = db_service.get_admin_user_by_username(db, "admin")
        if not existing:
            pw = generate_password_hash(os.getenv("ADMIN_PASSWORD", "Admin1234!"))
            db_service.create_admin_user(db, "admin", pw, role="admin")
            logger.info("✅ Default admin felhasználó létrehozva (felhasználó: admin)")
    finally:
        db.close()


if __name__ == "__main__":
    _bootstrap()
    app.run(host="0.0.0.0", port=8080, debug=False)
