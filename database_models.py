"""
SQLAlchemy adatbázis modellek a Credit Scoring rendszerhez.
Táblák: Customer, Prediction, ModelVersion, AdminUser
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, Text, ForeignKey, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    industry_code = Column(String(100), nullable=True)
    legal_entity_type = Column(String(100), nullable=True)
    net_sales = Column(Float, nullable=True)
    operating_margin = Column(Float, nullable=True)
    current_ratio = Column(Float, nullable=True)
    debt_to_equity = Column(Float, nullable=True)
    return_on_assets = Column(Float, nullable=True)
    late_payment_count = Column(Integer, default=0)
    description = Column(Text, nullable=True)

    # Vállalati jellemzők
    num_employees = Column(Integer, nullable=True)        # Alkalmazottak száma
    business_age = Column(Integer, nullable=True)         # Vállalkozás kora (év)
    client_segment = Column(String(100), nullable=True)   # Ügyfélszegmens (Micro/SME/Corporate)
    address_county = Column(String(100), nullable=True)   # Székhely megye

    # Mérleg adatok
    total_assets = Column(Float, nullable=True)           # Összes eszköz
    total_liabs = Column(Float, nullable=True)            # Összes kötelezettség
    current_assets = Column(Float, nullable=True)         # Forgóeszközök
    current_liabs = Column(Float, nullable=True)          # Rövid lejáratú kötelezettségek
    retained_earnings = Column(Float, nullable=True)      # Eredménytartalék
    collateral_value = Column(Float, nullable=True)       # Fedezet értéke

    # Eredménykimutatás
    ebit = Column(Float, nullable=True)                   # EBIT (adózás és kamat előtti eredmény)
    gross_margin = Column(Float, nullable=True)           # Bruttó marzs (%)
    annual_revenue_growth = Column(Float, nullable=True)  # Éves árbevétel növekedés (%)

    # Pénzügyi aránymutatók (kiegészítők)
    return_on_equity = Column(Float, nullable=True)       # ROE – saját tőke megtérülése (%)
    quick_ratio = Column(Float, nullable=True)            # Gyorslikviditási mutató
    working_capital = Column(Float, nullable=True)        # Forgótőke (Ft)
    days_sales_outstanding = Column(Float, nullable=True) # DSO – vevők átlagos fizetési ideje (nap)
    operating_cash_flow_ratio = Column(Float, nullable=True)  # Működési CF / Rövid lej. kötelezettségek
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    predictions = relationship("Prediction", back_populates="customer", cascade="all, delete-orphan")
    loan_applications = relationship("LoanApplication", back_populates="customer", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "email": self.email,
            "industry_code": self.industry_code,
            "legal_entity_type": self.legal_entity_type,
            "net_sales": self.net_sales,
            "operating_margin": self.operating_margin,
            "current_ratio": self.current_ratio,
            "debt_to_equity": self.debt_to_equity,
            "return_on_assets": self.return_on_assets,
            "late_payment_count": self.late_payment_count,
            "description": self.description,
            "num_employees": self.num_employees,
            "business_age": self.business_age,
            "client_segment": self.client_segment,
            "address_county": self.address_county,
            "total_assets": self.total_assets,
            "total_liabs": self.total_liabs,
            "current_assets": self.current_assets,
            "current_liabs": self.current_liabs,
            "retained_earnings": self.retained_earnings,
            "collateral_value": self.collateral_value,
            "ebit": self.ebit,
            "gross_margin": self.gross_margin,
            "annual_revenue_growth": self.annual_revenue_growth,
            "return_on_equity": self.return_on_equity,
            "quick_ratio": self.quick_ratio,
            "working_capital": self.working_capital,
            "days_sales_outstanding": self.days_sales_outstanding,
            "operating_cash_flow_ratio": self.operating_cash_flow_ratio,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    model_version = Column(String(100), nullable=True)
    mlflow_run_id = Column(String(255), nullable=True)

    # Eredmény
    prediction = Column(Integer, nullable=False)        # 0 = Non-Default, 1 = Default
    prediction_label = Column(String(50), nullable=True) # "DEFAULT" / "NON-DEFAULT"
    probability_of_default = Column(Float, nullable=False)

    # Shadow / Challenger adatok
    challenger_prediction = Column(Integer, nullable=True)
    challenger_probability = Column(Float, nullable=True)
    models_agree = Column(Boolean, nullable=True)

    # NLP
    sentiment_score = Column(Float, nullable=True)
    bias_detected = Column(Boolean, default=False)

    # Input snapshot (JSON)
    input_data = Column(JSON, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="predictions")

    def to_dict(self):
        return {
            "id": str(self.id),
            "customer_id": str(self.customer_id) if self.customer_id else None,
            "model_version": self.model_version,
            "mlflow_run_id": self.mlflow_run_id,
            "prediction": self.prediction,
            "prediction_label": self.prediction_label,
            "probability_of_default": self.probability_of_default,
            "challenger_prediction": self.challenger_prediction,
            "challenger_probability": self.challenger_probability,
            "models_agree": self.models_agree,
            "sentiment_score": self.sentiment_score,
            "bias_detected": self.bias_detected,
            "input_data": self.input_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LoanApplication(Base):
    """Hiteligény benyújtás és elbírálási workflow."""
    __tablename__ = "loan_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    prediction_id = Column(UUID(as_uuid=True), ForeignKey("predictions.id"), nullable=True)

    # Hiteligény adatok
    requested_amount = Column(Float, nullable=False)       # Igényelt összeg (Ft)
    loan_purpose = Column(String(255), nullable=True)      # Hitelcél
    loan_term_months = Column(Integer, nullable=True)      # Futamidő (hónap)
    notes = Column(Text, nullable=True)                    # Kérelmező megjegyzése

    # Státusz: pending → scored → approved / rejected / manual_review
    status = Column(String(50), default="pending")

    # Elbírálás
    decision_notes = Column(Text, nullable=True)
    decided_by = Column(String(100), nullable=True)
    decided_at = Column(DateTime, nullable=True)

    # Előzmény (a scoring időpontjában rögzített)
    prior_rejections = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="loan_applications")
    prediction = relationship("Prediction")

    def to_dict(self):
        return {
            "id": str(self.id),
            "customer_id": str(self.customer_id),
            "prediction_id": str(self.prediction_id) if self.prediction_id else None,
            "requested_amount": self.requested_amount,
            "loan_purpose": self.loan_purpose,
            "loan_term_months": self.loan_term_months,
            "notes": self.notes,
            "status": self.status,
            "decision_notes": self.decision_notes,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "prior_rejections": self.prior_rejections,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = Column(String(100), nullable=False)     # "Credit_Scoring_Champion"
    version = Column(String(50), nullable=True)
    mlflow_run_id = Column(String(255), nullable=True)

    # Metrikák
    champion_accuracy = Column(Float, nullable=True)
    champion_precision = Column(Float, nullable=True)
    champion_recall = Column(Float, nullable=True)
    champion_f1 = Column(Float, nullable=True)
    champion_roc_auc = Column(Float, nullable=True)

    challenger_accuracy = Column(Float, nullable=True)
    challenger_f1 = Column(Float, nullable=True)
    challenger_roc_auc = Column(Float, nullable=True)

    # Státusz: "staging", "production", "archived"
    status = Column(String(50), default="staging")

    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": str(self.id),
            "model_name": self.model_name,
            "version": self.version,
            "mlflow_run_id": self.mlflow_run_id,
            "champion_f1": self.champion_f1,
            "champion_roc_auc": self.champion_roc_auc,
            "challenger_f1": self.challenger_f1,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="analyst")   # "admin", "analyst", "viewer"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": str(self.id),
            "username": self.username,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
