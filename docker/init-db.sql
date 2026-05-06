-- ============================================================
-- Credit Scoring DB - Inicializáló SQL
-- Futtatja: PostgreSQL docker-entrypoint-initdb.d/ (csak első indulásnál)
-- ============================================================

-- MLflow adatbázis létrehozása
CREATE DATABASE mlflow_db;
GRANT ALL PRIVILEGES ON DATABASE mlflow_db TO credit_user;

-- Megjegyzés: A credit_scoring_db tábláit a SQLAlchemy (init_db()) hozza létre.
