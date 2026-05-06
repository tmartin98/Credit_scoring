"""
CRUD service - Ügyfél, Predikció és Modellverzió adatbázis műveletek.
"""
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database_models import Customer, Prediction, ModelVersion, AdminUser, LoanApplication


# -------------------------------------------------------
# CUSTOMER
# -------------------------------------------------------

def create_customer(db: Session, data: Dict[str, Any]) -> Customer:
    customer = Customer(
        name=data["name"],
        email=data.get("email"),
        industry_code=data.get("Industry_code") or data.get("industry_code"),
        legal_entity_type=data.get("legal_entity_type"),
        net_sales=data.get("NetSales") or data.get("net_sales"),
        operating_margin=data.get("Operating Margin") or data.get("operating_margin"),
        current_ratio=data.get("Current Ratio") or data.get("current_ratio"),
        debt_to_equity=data.get("DebtToEquityRatio") or data.get("debt_to_equity"),
        return_on_assets=data.get("Return on Assets (ROA)") or data.get("return_on_assets"),
        late_payment_count=data.get("LatePaymentCount") or data.get("late_payment_count") or 0,
        description=data.get("description"),
        # Vállalati jellemzők
        num_employees=data.get("num_employees"),
        business_age=data.get("BusinessAge") or data.get("business_age"),
        client_segment=data.get("pl_subseg_desc") or data.get("client_segment"),
        address_county=data.get("address_county"),
        # Mérleg
        total_assets=data.get("TotalAssets") or data.get("total_assets"),
        total_liabs=data.get("TotalLiabs") or data.get("total_liabs"),
        current_assets=data.get("CurrentAssets") or data.get("current_assets"),
        current_liabs=data.get("CurrentLiabs") or data.get("current_liabs"),
        retained_earnings=data.get("RetainedEarnings") or data.get("retained_earnings"),
        collateral_value=data.get("collateral_value"),
        # Eredménykimutatás
        ebit=data.get("EBIT") or data.get("ebit"),
        gross_margin=data.get("GrossMargin") or data.get("gross_margin"),
        annual_revenue_growth=data.get("AnnualRevenueGrowth") or data.get("annual_revenue_growth"),
        # Aránymutatók
        return_on_equity=data.get("Return on Equity (ROE)") or data.get("return_on_equity"),
        quick_ratio=data.get("QuickRatio") or data.get("quick_ratio"),
        working_capital=data.get("WorkingCapital") or data.get("working_capital"),
        days_sales_outstanding=data.get("DaysSalesOutstanding (DSO)") or data.get("days_sales_outstanding"),
        operating_cash_flow_ratio=data.get("OperatingCashFlowRatio") or data.get("operating_cash_flow_ratio"),
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def get_customer(db: Session, customer_id: str) -> Optional[Customer]:
    return db.query(Customer).filter(Customer.id == uuid.UUID(customer_id)).first()


def get_all_customers(db: Session, skip: int = 0, limit: int = 100) -> List[Customer]:
    return db.query(Customer).order_by(desc(Customer.created_at)).offset(skip).limit(limit).all()


def update_customer(db: Session, customer_id: str, data: Dict[str, Any]) -> Optional[Customer]:
    customer = get_customer(db, customer_id)
    if not customer:
        return None
    for key, value in data.items():
        if hasattr(customer, key):
            setattr(customer, key, value)
    customer.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(customer)
    return customer


def delete_customer(db: Session, customer_id: str) -> bool:
    customer = get_customer(db, customer_id)
    if not customer:
        return False
    db.delete(customer)
    db.commit()
    return True


def search_customers(db: Session, query: str, limit: int = 50) -> List[Customer]:
    return (
        db.query(Customer)
        .filter(Customer.name.ilike(f"%{query}%") | Customer.email.ilike(f"%{query}%"))
        .limit(limit)
        .all()
    )


# -------------------------------------------------------
# PREDICTION
# -------------------------------------------------------

def save_prediction(
    db: Session,
    prediction_result: Dict[str, Any],
    input_data: Dict[str, Any],
    customer_id: Optional[str] = None,
    model_version: Optional[str] = None,
    mlflow_run_id: Optional[str] = None,
) -> Prediction:
    shadow = prediction_result.get("shadow_meta", {})
    pred_label = "DEFAULT" if prediction_result["prediction"] == 1 else "NON-DEFAULT"

    prediction = Prediction(
        customer_id=uuid.UUID(customer_id) if customer_id else None,
        model_version=model_version,
        mlflow_run_id=mlflow_run_id,
        prediction=prediction_result["prediction"],
        prediction_label=pred_label,
        probability_of_default=prediction_result["pd_score"],
        challenger_prediction=shadow.get("challenger_prediction"),
        challenger_probability=shadow.get("challenger_pd"),
        models_agree=shadow.get("agreement"),
        sentiment_score=shadow.get("sentiment_score"),
        bias_detected=shadow.get("bias_detected", False),
        input_data=input_data,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def get_prediction(db: Session, prediction_id: str) -> Optional[Prediction]:
    return db.query(Prediction).filter(Prediction.id == uuid.UUID(prediction_id)).first()


def get_predictions_for_customer(db: Session, customer_id: str, limit: int = 50) -> List[Prediction]:
    return (
        db.query(Prediction)
        .filter(Prediction.customer_id == uuid.UUID(customer_id))
        .order_by(desc(Prediction.created_at))
        .limit(limit)
        .all()
    )


def get_recent_predictions(db: Session, limit: int = 100) -> List[Prediction]:
    return db.query(Prediction).order_by(desc(Prediction.created_at)).limit(limit).all()


def get_predictions_stats(db: Session) -> Dict[str, Any]:
    total = db.query(Prediction).count()
    defaults = db.query(Prediction).filter(Prediction.prediction == 1).count()
    biased = db.query(Prediction).filter(Prediction.bias_detected == True).count()
    return {
        "total": total,
        "defaults": defaults,
        "non_defaults": total - defaults,
        "default_rate": round(defaults / total, 4) if total > 0 else 0.0,
        "bias_detections": biased,
    }


# -------------------------------------------------------
# MODEL VERSION
# -------------------------------------------------------

def save_model_version(db: Session, data: Dict[str, Any]) -> ModelVersion:
    champ = data.get("champion", {})
    chall = data.get("challenger", {})
    mv = ModelVersion(
        model_name=data.get("model_name", "Credit_Scoring_Champion"),
        version=data.get("version"),
        mlflow_run_id=data.get("mlflow_run_id"),
        champion_accuracy=champ.get("accuracy"),
        champion_precision=champ.get("precision"),
        champion_recall=champ.get("recall"),
        champion_f1=champ.get("f1_score"),
        champion_roc_auc=champ.get("roc_auc"),
        challenger_accuracy=chall.get("accuracy"),
        challenger_f1=chall.get("f1_score"),
        challenger_roc_auc=chall.get("roc_auc"),
        status="staging",
    )
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return mv


def get_model_versions(db: Session, limit: int = 20) -> List[ModelVersion]:
    return db.query(ModelVersion).order_by(desc(ModelVersion.created_at)).limit(limit).all()


def promote_model_version(db: Session, version_id: str) -> Optional[ModelVersion]:
    db.query(ModelVersion).filter(ModelVersion.status == "production").update({"status": "archived"})
    mv = db.query(ModelVersion).filter(ModelVersion.id == uuid.UUID(version_id)).first()
    if mv:
        mv.status = "production"
        db.commit()
        db.refresh(mv)
    return mv


def get_production_model(db: Session) -> Optional[ModelVersion]:
    return db.query(ModelVersion).filter(ModelVersion.status == "production").order_by(desc(ModelVersion.created_at)).first()


# -------------------------------------------------------
# ADMIN USER
# -------------------------------------------------------

def get_admin_user_by_username(db: Session, username: str) -> Optional[AdminUser]:
    return db.query(AdminUser).filter(AdminUser.username == username).first()


def create_admin_user(db: Session, username: str, password_hash: str, role: str = "analyst") -> AdminUser:
    user = AdminUser(username=username, password_hash=password_hash, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_last_login(db: Session, user: AdminUser):
    user.last_login = datetime.utcnow()
    db.commit()


# -------------------------------------------------------
# LOAN APPLICATION
# -------------------------------------------------------

def create_loan_application(db: Session, data: Dict[str, Any]) -> LoanApplication:
    app = LoanApplication(
        customer_id=uuid.UUID(data["customer_id"]),
        requested_amount=data["requested_amount"],
        loan_purpose=data.get("loan_purpose"),
        loan_term_months=data.get("loan_term_months"),
        notes=data.get("notes"),
        status="pending",
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def get_loan_application(db: Session, app_id: str) -> Optional[LoanApplication]:
    return db.query(LoanApplication).filter(LoanApplication.id == uuid.UUID(app_id)).first()


def get_loan_applications_for_customer(db: Session, customer_id: str, limit: int = 50) -> List[LoanApplication]:
    return (
        db.query(LoanApplication)
        .filter(LoanApplication.customer_id == uuid.UUID(customer_id))
        .order_by(desc(LoanApplication.created_at))
        .limit(limit)
        .all()
    )


def get_all_loan_applications(db: Session, limit: int = 200, status_filter: Optional[str] = None) -> List[LoanApplication]:
    q = db.query(LoanApplication)
    if status_filter:
        q = q.filter(LoanApplication.status == status_filter)
    return q.order_by(desc(LoanApplication.created_at)).limit(limit).all()


def count_rejections_for_customer(db: Session, customer_id: str) -> int:
    return (
        db.query(LoanApplication)
        .filter(
            LoanApplication.customer_id == uuid.UUID(customer_id),
            LoanApplication.status == "rejected",
        )
        .count()
    )


def link_prediction_to_application(db: Session, app_id: str, prediction_id: str, prior_rejections: int) -> Optional[LoanApplication]:
    app = get_loan_application(db, app_id)
    if not app:
        return None
    app.prediction_id = uuid.UUID(prediction_id)
    app.prior_rejections = prior_rejections
    app.status = "scored"
    app.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(app)
    return app


def decide_loan_application(
    db: Session,
    app_id: str,
    decision: str,
    decision_notes: Optional[str],
    decided_by: str,
) -> Optional[LoanApplication]:
    app = get_loan_application(db, app_id)
    if not app:
        return None
    app.status = decision  # "approved" / "rejected" / "manual_review"
    app.decision_notes = decision_notes
    app.decided_by = decided_by
    app.decided_at = datetime.utcnow()
    app.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(app)
    return app
