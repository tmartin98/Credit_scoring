"""
Admin felület - Flask-Admin alapú adminisztráció.
Ügyfélkezelés, predikciós előzmények és modellverzió-kezelés.
"""
import os
import functools
import logging
from datetime import datetime

import mlflow

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

from database import SessionLocal
import db_service

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY", "credit_admin_secret_2024")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5102")


# -------------------------------------------------------
# Auth decorator
# -------------------------------------------------------

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


# -------------------------------------------------------
# Auth routes
# -------------------------------------------------------

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        db = SessionLocal()
        try:
            user = db_service.get_admin_user_by_username(db, username)
            if user and user.is_active and check_password_hash(user.password_hash, password):
                session["admin_logged_in"] = True
                session["admin_user"] = username
                session["admin_role"] = user.role
                db_service.update_last_login(db, user)
                return redirect(url_for("admin.dashboard"))
            flash("Hibás felhasználónév vagy jelszó.", "error")
        finally:
            db.close()
    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


# -------------------------------------------------------
# Dashboard
# -------------------------------------------------------

@admin_bp.route("/")
@admin_bp.route("/dashboard")
@login_required
def dashboard():
    db = SessionLocal()
    try:
        stats = db_service.get_predictions_stats(db)
        recent_predictions = db_service.get_recent_predictions(db, limit=10)
        recent_customers = db_service.get_all_customers(db, limit=5)
        model_versions = db_service.get_model_versions(db, limit=5)
        prod_model = db_service.get_production_model(db)
        all_customers_list = db_service.get_all_customers(db, limit=9999)

        # Hiteligény statisztikák
        all_loans = db_service.get_all_loan_applications(db, limit=9999)
        loan_stats = {
            "total": len(all_loans),
            "pending":  sum(1 for l in all_loans if l.status == "pending"),
            "scored":   sum(1 for l in all_loans if l.status == "scored"),
            "approved": sum(1 for l in all_loans if l.status == "approved"),
            "rejected": sum(1 for l in all_loans if l.status == "rejected"),
            "manual":   sum(1 for l in all_loans if l.status == "manual_review"),
        }

        # Ügyfelek JSON az összehasonlító diagramhoz
        import json as _json
        customers_json = _json.dumps([
            {
                "id": str(c.id),
                "name": c.name,
                "industry_code": c.industry_code or "—",
                "legal_entity_type": c.legal_entity_type or "—",
                "operating_margin":        c.operating_margin or 0,
                "return_on_assets":        c.return_on_assets or 0,
                "return_on_equity":        c.return_on_equity or 0,
                "current_ratio":           c.current_ratio or 0,
                "quick_ratio":             c.quick_ratio or 0,
                "debt_to_equity":          c.debt_to_equity or 0,
                "gross_margin":            c.gross_margin or 0,
                "annual_revenue_growth":   c.annual_revenue_growth or 0,
                "operating_cash_flow_ratio": c.operating_cash_flow_ratio or 0,
                "late_payment_count":      c.late_payment_count or 0,
            }
            for c in all_customers_list
        ])

        return render_template(
            "admin/dashboard.html",
            stats=stats,
            recent_predictions=recent_predictions,
            recent_customers=recent_customers,
            model_versions=model_versions,
            prod_model=prod_model,
            total_customers=len(all_customers_list),
            loan_stats=loan_stats,
            customers_json=customers_json,
        )
    finally:
        db.close()


# -------------------------------------------------------
# Customers
# -------------------------------------------------------

@admin_bp.route("/customers/create", methods=["GET", "POST"])
@login_required
def create_customer():
    if request.method == "POST":
        data = {
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip() or None,
            "Industry_code": request.form.get("industry_code", "").strip() or None,
            "legal_entity_type": request.form.get("legal_entity_type", "").strip() or None,
            "NetSales": _to_float(request.form.get("net_sales")),
            "Operating Margin": _to_float(request.form.get("operating_margin")),
            "Current Ratio": _to_float(request.form.get("current_ratio")),
            "DebtToEquityRatio": _to_float(request.form.get("debt_to_equity")),
            "Return on Assets (ROA)": _to_float(request.form.get("return_on_assets")),
            "LatePaymentCount": int(request.form.get("late_payment_count") or 0),
            "description": request.form.get("description", "").strip() or None,
            # Vállalati jellemzők
            "num_employees": int(request.form.get("num_employees") or 0) or None,
            "BusinessAge": int(request.form.get("business_age") or 0) or None,
            "pl_subseg_desc": request.form.get("client_segment", "").strip() or None,
            "address_county": request.form.get("address_county", "").strip() or None,
            # Mérleg
            "TotalAssets": _to_float(request.form.get("total_assets")),
            "TotalLiabs": _to_float(request.form.get("total_liabs")),
            "CurrentAssets": _to_float(request.form.get("current_assets")),
            "CurrentLiabs": _to_float(request.form.get("current_liabs")),
            "RetainedEarnings": _to_float(request.form.get("retained_earnings")),
            "collateral_value": _to_float(request.form.get("collateral_value")),
            # Eredménykimutatás
            "EBIT": _to_float(request.form.get("ebit")),
            "GrossMargin": _to_float(request.form.get("gross_margin")),
            "AnnualRevenueGrowth": _to_float(request.form.get("annual_revenue_growth")),
            # Aránymutatók
            "Return on Equity (ROE)": _to_float(request.form.get("return_on_equity")),
            "QuickRatio": _to_float(request.form.get("quick_ratio")),
            "WorkingCapital": _to_float(request.form.get("working_capital")),
            "DaysSalesOutstanding (DSO)": _to_float(request.form.get("days_sales_outstanding")),
            "OperatingCashFlowRatio": _to_float(request.form.get("operating_cash_flow_ratio")),
        }
        if not data["name"]:
            flash("A név megadása kötelező.", "error")
            return render_template("admin/customer_form.html")
        db = SessionLocal()
        try:
            customer = db_service.create_customer(db, data)
            flash(f"'{customer.name}' ügyfél sikeresen létrehozva.", "success")
            return redirect(url_for("admin.customer_detail", customer_id=str(customer.id)))
        except Exception as e:
            flash(f"Hiba az ügyfél mentésekor: {e}", "error")
        finally:
            db.close()
    return render_template("admin/customer_form.html")


@admin_bp.route("/customers/<customer_id>/predict", methods=["GET", "POST"])
@login_required
def customer_predict(customer_id):
    db = SessionLocal()
    try:
        customer = db_service.get_customer(db, customer_id)
        if not customer:
            flash("Ügyfél nem található.", "error")
            return redirect(url_for("admin.customers"))
    finally:
        db.close()

    if request.method == "POST":
        app_data = {
            "NetSales": _to_float(request.form.get("net_sales")),
            "Operating Margin": _to_float(request.form.get("operating_margin")),
            "Current Ratio": _to_float(request.form.get("current_ratio")),
            "DebtToEquityRatio": _to_float(request.form.get("debt_to_equity")),
            "Return on Assets (ROA)": _to_float(request.form.get("return_on_assets")),
            "LatePaymentCount": int(request.form.get("late_payment_count") or 0),
            "description": request.form.get("description", "").strip() or None,
            "Industry_code": request.form.get("industry_code", "").strip() or None,
            "legal_entity_type": request.form.get("legal_entity_type", "").strip() or None,
            "num_employees": int(request.form.get("num_employees") or 0) or None,
            "BusinessAge": int(request.form.get("business_age") or 0) or None,
            "pl_subseg_desc": request.form.get("client_segment", "").strip() or None,
            "address_county": request.form.get("address_county", "").strip() or None,
            "TotalAssets": _to_float(request.form.get("total_assets")),
            "TotalLiabs": _to_float(request.form.get("total_liabs")),
            "CurrentAssets": _to_float(request.form.get("current_assets")),
            "CurrentLiabs": _to_float(request.form.get("current_liabs")),
            "RetainedEarnings": _to_float(request.form.get("retained_earnings")),
            "collateral_value": _to_float(request.form.get("collateral_value")),
            "EBIT": _to_float(request.form.get("ebit")),
            "GrossMargin": _to_float(request.form.get("gross_margin")),
            "AnnualRevenueGrowth": _to_float(request.form.get("annual_revenue_growth")),
            "Return on Equity (ROE)": _to_float(request.form.get("return_on_equity")),
            "QuickRatio": _to_float(request.form.get("quick_ratio")),
            "WorkingCapital": _to_float(request.form.get("working_capital")),
            "DaysSalesOutstanding (DSO)": _to_float(request.form.get("days_sales_outstanding")),
            "OperatingCashFlowRatio": _to_float(request.form.get("operating_cash_flow_ratio")),
        }
        try:
            # Közvetlen ML + DB hívás (nem HTTP loop)
            from MLModel import CreditScoringModel
            from mlflow.tracking import MlflowClient
            mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
            ml_client = MlflowClient()
            model = CreditScoringModel(client=ml_client)
            result = model.predict_shadow_mode(app_data)

            run_id = None
            try:
                with mlflow.start_run(run_name="admin_scoring") as run:
                    mlflow.log_param("customer_id", customer_id)
                    mlflow.log_metric("prob_default", result["pd_score"])
                    mlflow.log_dict(result, "scoring_result.json")
                    run_id = run.info.run_id
            except Exception as e:
                logger.warning("MLflow log hiba: %s", e)

            db = SessionLocal()
            try:
                prod = db_service.get_production_model(db)
                pred_record = db_service.save_prediction(
                    db,
                    prediction_result=result,
                    input_data=app_data,
                    customer_id=customer_id,
                    model_version=prod.version if prod else None,
                    mlflow_run_id=run_id,
                )
                flash(
                    f"✅ Predikció: {'DEFAULT' if result['prediction'] == 1 else 'NON-DEFAULT'} "
                    f"(PD: {result['pd_score']:.4f})",
                    "success" if result["prediction"] == 0 else "error"
                )
                return redirect(url_for("admin.customer_detail", customer_id=customer_id))
            finally:
                db.close()
        except Exception as e:
            logger.error("Predikció hiba: %s", e, exc_info=True)
            flash(f"Predikciós hiba: {e}", "error")

    return render_template("admin/customer_predict.html", customer=customer)


def _to_float(val):
    try:
        return float(val) if val else None
    except (ValueError, TypeError):
        return None


@admin_bp.route("/customers")
@login_required
def customers():
    db = SessionLocal()
    try:
        search_q = request.args.get("q", "")
        if search_q:
            customers_list = db_service.search_customers(db, search_q)
        else:
            customers_list = db_service.get_all_customers(db, limit=200)
        return render_template("admin/customers.html", customers=customers_list, search_q=search_q)
    finally:
        db.close()


@admin_bp.route("/customers/<customer_id>")
@login_required
def customer_detail(customer_id):
    db = SessionLocal()
    try:
        customer = db_service.get_customer(db, customer_id)
        if not customer:
            flash("Ügyfél nem található.", "error")
            return redirect(url_for("admin.customers"))
        predictions = db_service.get_predictions_for_customer(db, customer_id)
        return render_template("admin/customer_detail.html", customer=customer, predictions=predictions)
    finally:
        db.close()


@admin_bp.route("/customers/<customer_id>/delete", methods=["POST"])
@login_required
def delete_customer(customer_id):
    if session.get("admin_role") not in ("admin",):
        flash("Nincs jogosultságod ehhez a művelethez.", "error")
        return redirect(url_for("admin.customers"))
    db = SessionLocal()
    try:
        db_service.delete_customer(db, customer_id)
        flash("Ügyfél törölve.", "success")
    finally:
        db.close()
    return redirect(url_for("admin.customers"))


# -------------------------------------------------------
# Predictions
# -------------------------------------------------------

@admin_bp.route("/predictions")
@login_required
def predictions():
    db = SessionLocal()
    try:
        preds = db_service.get_recent_predictions(db, limit=200)
        stats = db_service.get_predictions_stats(db)
        return render_template("admin/predictions.html", predictions=preds, stats=stats)
    finally:
        db.close()


@admin_bp.route("/predictions/<prediction_id>")
@login_required
def prediction_detail(prediction_id):
    db = SessionLocal()
    try:
        pred = db_service.get_prediction(db, prediction_id)
        if not pred:
            flash("Predikció nem található.", "error")
            return redirect(url_for("admin.predictions"))
        return render_template("admin/prediction_detail.html", pred=pred)
    finally:
        db.close()


# -------------------------------------------------------
# Model Versions
# -------------------------------------------------------

@admin_bp.route("/models")
@login_required
def model_versions():
    db = SessionLocal()
    try:
        versions = db_service.get_model_versions(db, limit=50)
        prod_model = db_service.get_production_model(db)
        return render_template("admin/model_versions.html", versions=versions, prod_model=prod_model)
    finally:
        db.close()


@admin_bp.route("/models/<version_id>/promote", methods=["POST"])
@login_required
def promote_model(version_id):
    if session.get("admin_role") not in ("admin",):
        flash("Nincs jogosultságod ehhez a művelethez.", "error")
        return redirect(url_for("admin.model_versions"))
    db = SessionLocal()
    try:
        mv = db_service.promote_model_version(db, version_id)
        if mv:
            flash(f"Modell v{mv.version} élesítve (production).", "success")
        else:
            flash("Modellverzió nem található.", "error")
    finally:
        db.close()
    return redirect(url_for("admin.model_versions"))


# -------------------------------------------------------
# Users (csak admin szerepkör)
# -------------------------------------------------------

@admin_bp.route("/users")
@login_required
def users():
    if session.get("admin_role") != "admin":
        flash("Hozzáférés megtagadva.", "error")
        return redirect(url_for("admin.dashboard"))
    db = SessionLocal()
    try:
        from database_models import AdminUser
        users_list = db.query(AdminUser).all()
        return render_template("admin/users.html", users=users_list)
    finally:
        db.close()


@admin_bp.route("/users/create", methods=["POST"])
@login_required
def create_user():
    if session.get("admin_role") != "admin":
        return jsonify({"error": "Hozzáférés megtagadva"}), 403
    username = request.form.get("username")
    password = request.form.get("password")
    role = request.form.get("role", "analyst")
    if not username or not password:
        flash("Felhasználónév és jelszó kötelező.", "error")
        return redirect(url_for("admin.users"))
    db = SessionLocal()
    try:
        pw_hash = generate_password_hash(password)
        db_service.create_admin_user(db, username, pw_hash, role)
        flash(f"Felhasználó '{username}' létrehozva.", "success")
    except Exception as e:
        flash(f"Hiba: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("admin.users"))


# -------------------------------------------------------
# Loan Applications (Hiteligények)
# -------------------------------------------------------

LOAN_PURPOSES = [
    "Beruházási hitel",
    "Forgóeszköz hitel",
    "Ingatlanvásárlás",
    "Eszközfinanszírozás",
    "Folyószámlahitel",
    "Egyéb",
]

STATUS_LABELS = {
    "pending": ("Függőben", "secondary"),
    "scored": ("Kreditbírálat kész", "info"),
    "approved": ("Jóváhagyva", "success"),
    "rejected": ("Elutasítva", "danger"),
    "manual_review": ("Kézi elbírálás", "warning"),
}


@admin_bp.route("/loan-applications")
@login_required
def loan_applications():
    db = SessionLocal()
    try:
        status_filter = request.args.get("status", "")
        apps = db_service.get_all_loan_applications(db, limit=200, status_filter=status_filter or None)
        return render_template(
            "admin/loan_applications.html",
            apps=apps,
            status_filter=status_filter,
            status_labels=STATUS_LABELS,
        )
    finally:
        db.close()


@admin_bp.route("/loan-applications/create", methods=["GET", "POST"])
@login_required
def create_loan_application():
    db = SessionLocal()
    try:
        customers_list = db_service.get_all_customers(db, limit=500)
    finally:
        db.close()

    if request.method == "POST":
        customer_id = request.form.get("customer_id", "").strip()
        amount = _to_float(request.form.get("requested_amount"))
        if not customer_id or not amount:
            flash("Ügyfél és igényelt összeg megadása kötelező.", "error")
            return render_template(
                "admin/loan_application_form.html",
                customers=customers_list,
                loan_purposes=LOAN_PURPOSES,
            )
        data = {
            "customer_id": customer_id,
            "requested_amount": amount,
            "loan_purpose": request.form.get("loan_purpose") or None,
            "loan_term_months": int(request.form.get("loan_term_months") or 0) or None,
            "notes": request.form.get("notes", "").strip() or None,
        }
        db = SessionLocal()
        try:
            app = db_service.create_loan_application(db, data)
            flash("Hiteligény sikeresen benyújtva.", "success")
            return redirect(url_for("admin.loan_application_detail", app_id=str(app.id)))
        except Exception as e:
            flash(f"Hiba: {e}", "error")
        finally:
            db.close()

    return render_template(
        "admin/loan_application_form.html",
        customers=customers_list,
        loan_purposes=LOAN_PURPOSES,
    )


@admin_bp.route("/loan-applications/<app_id>")
@login_required
def loan_application_detail(app_id):
    db = SessionLocal()
    try:
        app = db_service.get_loan_application(db, app_id)
        if not app:
            flash("Hiteligény nem található.", "error")
            return redirect(url_for("admin.loan_applications"))
        return render_template(
            "admin/loan_application_detail.html",
            app=app,
            status_labels=STATUS_LABELS,
        )
    finally:
        db.close()


@admin_bp.route("/loan-applications/<app_id>/score", methods=["POST"])
@login_required
def score_loan_application(app_id):
    """Kreditbírálat futtatása: a tárolt ügyfél adatai alapján predikciót készít,
    a prior_rejections értéket feature-ként adja át a modellnek."""
    db = SessionLocal()
    try:
        app = db_service.get_loan_application(db, app_id)
        if not app:
            flash("Hiteligény nem található.", "error")
            return redirect(url_for("admin.loan_applications"))
        if app.status in ("approved", "rejected"):
            flash("Már lezárt hiteligény nem minősíthető újra.", "warning")
            return redirect(url_for("admin.loan_application_detail", app_id=app_id))

        customer = app.customer
        prior_rejections = db_service.count_rejections_for_customer(db, str(customer.id))

        app_data = {
            "NetSales": customer.net_sales,
            "Operating Margin": customer.operating_margin,
            "Current Ratio": customer.current_ratio,
            "DebtToEquityRatio": customer.debt_to_equity,
            "Return on Assets (ROA)": customer.return_on_assets,
            "LatePaymentCount": customer.late_payment_count or 0,
            "prior_rejections": prior_rejections,
            "description": customer.description,
        }

        from MLModel import CreditScoringModel
        from mlflow.tracking import MlflowClient
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        ml_client = MlflowClient()
        model = CreditScoringModel(client=ml_client)
        result = model.predict_shadow_mode(app_data)

        run_id = None
        try:
            with mlflow.start_run(run_name="loan_app_scoring") as run:
                mlflow.log_param("customer_id", str(customer.id))
                mlflow.log_param("loan_application_id", app_id)
                mlflow.log_metric("prob_default", result["pd_score"])
                mlflow.log_metric("prior_rejections", prior_rejections)
                mlflow.log_dict(result, "scoring_result.json")
                run_id = run.info.run_id
        except Exception as e:
            logger.warning("MLflow log hiba: %s", e)

        prod = db_service.get_production_model(db)
        pred_record = db_service.save_prediction(
            db,
            prediction_result=result,
            input_data=app_data,
            customer_id=str(customer.id),
            model_version=prod.version if prod else None,
            mlflow_run_id=run_id,
        )
        db_service.link_prediction_to_application(db, app_id, str(pred_record.id), prior_rejections)

        flash(
            f"✅ Kreditbírálat kész: {'DEFAULT – Elutasít' if result['prediction'] == 1 else 'NON-DEFAULT – Elfogad'} "
            f"(PD: {result['pd_score']:.4f})",
            "success" if result["prediction"] == 0 else "error",
        )
    except Exception as e:
        logger.error("Loan scoring hiba: %s", e, exc_info=True)
        flash(f"Kreditbírálati hiba: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("admin.loan_application_detail", app_id=app_id))


@admin_bp.route("/loan-applications/<app_id>/decide", methods=["POST"])
@login_required
def decide_loan_application(app_id):
    """Hiteligény elbírálása: jóváhagyás, elutasítás, vagy kézi elbírálásra utalás."""
    decision = request.form.get("decision")
    if decision not in ("approved", "rejected", "manual_review"):
        flash("Érvénytelen döntés.", "error")
        return redirect(url_for("admin.loan_application_detail", app_id=app_id))
    db = SessionLocal()
    try:
        app = db_service.get_loan_application(db, app_id)
        if not app:
            flash("Hiteligény nem található.", "error")
            return redirect(url_for("admin.loan_applications"))
        if app.status == "pending":
            flash("Kreditbírálat elvégzése szükséges a döntés előtt.", "warning")
            return redirect(url_for("admin.loan_application_detail", app_id=app_id))
        db_service.decide_loan_application(
            db,
            app_id=app_id,
            decision=decision,
            decision_notes=request.form.get("decision_notes", "").strip() or None,
            decided_by=session.get("admin_user", "unknown"),
        )
        labels = {"approved": "Jóváhagyva", "rejected": "Elutasítva", "manual_review": "Kézi elbírálásra utalva"}
        flash(f"Döntés rögzítve: {labels.get(decision, decision)}", "success")
    except Exception as e:
        flash(f"Hiba: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("admin.loan_application_detail", app_id=app_id))
