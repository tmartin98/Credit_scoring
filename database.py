"""
Adatbázis konfiguráció és kapcsolatkezelés.
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from database_models import Base


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://credit_user:credit_pass@localhost:5432/credit_scoring_db"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency injection - adatbázis session lekérése."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Táblák létrehozása (ha nem léteznek) + meglévő táblák migrálása új oszlopokkal."""
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns()
    print("✅ Adatbázis táblák inicializálva.")


def _migrate_add_columns():
    """Idempotens migrációs segédfüggvény: új oszlopokat ad a customers táblához."""
    new_columns = [
        ("num_employees",            "INTEGER"),
        ("business_age",             "INTEGER"),
        ("client_segment",           "VARCHAR(100)"),
        ("address_county",           "VARCHAR(100)"),
        ("total_assets",             "DOUBLE PRECISION"),
        ("total_liabs",              "DOUBLE PRECISION"),
        ("current_assets",           "DOUBLE PRECISION"),
        ("current_liabs",            "DOUBLE PRECISION"),
        ("retained_earnings",        "DOUBLE PRECISION"),
        ("collateral_value",         "DOUBLE PRECISION"),
        ("ebit",                     "DOUBLE PRECISION"),
        ("gross_margin",             "DOUBLE PRECISION"),
        ("annual_revenue_growth",    "DOUBLE PRECISION"),
        ("return_on_equity",         "DOUBLE PRECISION"),
        ("quick_ratio",              "DOUBLE PRECISION"),
        ("working_capital",          "DOUBLE PRECISION"),
        ("days_sales_outstanding",   "DOUBLE PRECISION"),
        ("operating_cash_flow_ratio","DOUBLE PRECISION"),
    ]
    with engine.connect() as conn:
        for col_name, col_type in new_columns:
            try:
                conn.execute(text(
                    f"ALTER TABLE customers ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                ))
                conn.commit()
            except Exception:
                conn.rollback()


def check_db_connection() -> bool:
    """Adatbázis kapcsolat ellenőrzése."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"❌ DB kapcsolat hiba: {e}")
        return False
