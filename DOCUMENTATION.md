# Credit Scoring Rendszer — Technikai és Funkcionális Dokumentáció

> **Verzió:** 1.0  
> **Készítette:** Credit Scoring System projekt  
> **Célja:** Vállalati hitelkockázat-értékelés gépi tanulás alapú automatizálása

---

## Tartalomjegyzék

1. [Rendszeráttekintés](#1-rendszeráttekintés)
2. [Funkcionális követelmények](#2-funkcionális-követelmények)
3. [Rendszerarchitektúra](#3-rendszerarchitektúra)
4. [Komponensek részletes leírása](#4-komponensek-részletes-leírása)
5. [Gépi tanulási módszertan](#5-gépi-tanulási-módszertan)
6. [Adatbázis-séma](#6-adatbázis-séma)
7. [REST API dokumentáció](#7-rest-api-dokumentáció)
8. [Admin felület](#8-admin-felület)
9. [Hiteligény workflow](#9-hiteligény-workflow)
10. [Konténerizáció és üzembe helyezés](#10-konténerizáció-és-üzembe-helyezés)
11. [Biztonság és hozzáférés-kezelés](#11-biztonság-és-hozzáférés-kezelés)
12. [Minőségbiztosítás és monitoring](#12-minőségbiztosítás-és-monitoring)

---

## 1. Rendszeráttekintés

A Credit Scoring System egy **vállalati hitelkockázat-értékelő rendszer**, amely gépi tanulás segítségével automatizálja a hitelképességi döntéseket. A rendszer képes:

- Vállalati pénzügyi mutatók alapján **nemfizetési valószínűséget** (Probability of Default, PD) számítani
- Két gépi tanulási modell párhuzamos futtatásával (**Shadow System**) növelni a megbízhatóságot
- A szöveges ügyfélleírások **NLP-alapú sentiment elemzésével** kiegészíteni a kvantitatív értékelést
- Az összes döntést és modellverziót **auditálható formában** rögzíteni
- A hiteligénylési folyamatot **teljes workflow-ban** kezelni a benyújtástól a döntésig

### Főbb jellemzők

| Tulajdonság | Érték |
|---|---|
| Modell architektúra | Shadow System (Champion + Challenger) |
| Fő modell | XGBoost (Champion) |
| Kihívó modell | LightGBM (Challenger) |
| NLP modul | Sentiment analízis kulcsszó-alapon |
| Kísérletkövetés | MLflow |
| Pipeline ütemezés | Apache Airflow |
| Adatbázis | PostgreSQL 16 |
| API keretrendszer | Flask + Flask-RESTX (Swagger) |
| Konténerizáció | Docker Swarm |

---

## 2. Funkcionális követelmények

### 2.1 Hitelkockázat értékelés

- **FR-01:** A rendszer képes vállalati pénzügyi mutatók alapján bináris kockázati besorolást adni (magas / alacsony kockázat)
- **FR-02:** A rendszer valószínűségi pontszámot (0–1 skálán) ad a nemfizetési kockázatra
- **FR-03:** A rendszer két modell (Champion és Challenger) eredményét párhuzamosan számítja ki
- **FR-04:** Az eredmény tartalmaz NLP-alapú sentiment pontszámot a szöveges leírásból
- **FR-05:** A rendszer jelzi, ha a kvantitatív és szöveges értékelés ellentmond egymásnak (elfogultsági riasztás)

### 2.2 Modellkezelés

- **FR-06:** A modell tanítható CSV fájl feltöltésével REST API-n vagy Swagger UI-n keresztül
- **FR-07:** A tanítás Airflow DAG-on keresztül is indítható és ütemezthető
- **FR-08:** Minden tanítási kísérlet eredménye (metrikák, modell artefaktok) MLflow-ban kerül rögzítésre
- **FR-09:** A modellverziók promótálhatók staging → production státuszba

### 2.3 Ügyfélkezelés

- **FR-10:** Az ügyfelek CRUD műveletekkel kezelhetők (admin felületen és REST API-n)
- **FR-11:** Minden ügyfélhez rögzíthető: azonosítók, pénzügyi mutatók, szöveges leírás
- **FR-12:** Az ügyfél predikciós előzményei megtekinthetők

### 2.4 Hiteligény workflow

- **FR-13:** Hiteligény benyújtható meglévő ügyfélhez (igényelt összeg, cél, futamidő)
- **FR-14:** A kreditbírálat futtatható az ügyfél tárolt adatai alapján — az előző elutasítások száma automatikusan feature-ként kerül felhasználásra
- **FR-15:** A döntéshozó jóváhagyhatja, elutasíthatja, vagy kézi elbírálásra utalhatja a kérelmet
- **FR-16:** A kézi elbírálásra utalt kérelmek véglegesen dönthetők el (jóváhagyás / elutasítás)

### 2.5 Adminisztráció

- **FR-17:** Webes admin felület érhető el role-based access control-lal (admin / analyst / viewer)
- **FR-18:** Az admin felületen megtekinthetők a predikciós statisztikák (kockázati arány, elfogultsági jelzések)

---

## 3. Rendszerarchitektúra

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Swarm Cluster                      │
│                                                                   │
│  ┌──────────────┐    ┌──────────────────────────────────────┐   │
│  │   Airflow     │    │         Credit Scoring API            │   │
│  │  Webserver   │    │  (Flask + Flask-RESTX, 2 replika)    │   │
│  │  Scheduler   │───▶│                                       │   │
│  │  Worker      │    │  ┌──────────┐  ┌──────────────────┐  │   │
│  │  (Celery)    │    │  │ REST API │  │  Admin UI (Jinja) │  │   │
│  └──────┬───────┘    │  │ /scoring │  │  /admin/*         │  │   │
│         │            │  │ /api/*   │  └──────────────────┘  │   │
│         │ REST API   │  └────┬─────┘                        │   │
│         └───────────▶│       │                               │   │
│                       │  ┌────▼──────────────────────────┐  │   │
│                       │  │    CreditScoringModel           │  │   │
│                       │  │  Champion (XGBoost)            │  │   │
│                       │  │  Challenger (LightGBM)         │  │   │
│                       │  │  NLP Sentiment Analyzer        │  │   │
│                       │  └────┬──────────────────────┬───┘  │   │
│                       └───────┼──────────────────────┼───────┘   │
│                               │                      │           │
│         ┌─────────────────────▼──┐    ┌─────────────▼──────┐   │
│         │    PostgreSQL (App DB)  │    │   MLflow Server     │   │
│         │  customers             │    │  Kísérletkövetés    │   │
│         │  predictions           │    │  Modell registry    │   │
│         │  loan_applications     │    │  Artefakt tárolás   │   │
│         │  model_versions        │    └────────────────────┘   │
│         │  admin_users           │                              │
│         └────────────────────────┘                              │
│                                                                   │
│         ┌──────────────┐    ┌─────────────────────────────┐    │
│         │  PostgreSQL   │    │           Redis              │    │
│         │  (Airflow DB) │    │  (Celery message broker)    │    │
│         └──────────────┘    └─────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Hálózati rétegek

| Hálózat | Típus | Résztvevők |
|---|---|---|
| `credit_net` | Overlay | API, PostgreSQL (app), MLflow |
| `airflow_net` | Overlay | Airflow komponensek, Redis, API |

---

## 4. Komponensek részletes leírása

### 4.1 Flask REST API (`app.py`)

A rendszer belépési pontja. Flask + Flask-RESTX keretrendszerre épül, amely automatikus Swagger UI dokumentációt generál.

**Főbb feladatok:**
- HTTP végpontok kiszolgálása
- Fájl fogadása tanítási célra
- `CreditScoringModel` példányosítása és meghívása
- MLflow kísérlet indítása és metrikák logolása
- Adatbázis műveletek delegálása `db_service`-be
- Airflow REST API hívás tanítás triggereléshez

**Induláskor végrehajtott műveletek:**
1. PostgreSQL kapcsolat ellenőrzése
2. Adatbázistáblák létrehozása (`init_db()`)
3. Admin felhasználó létrehozása (ha nem létezik)
4. MLflow experiment létrehozása (ha nem létezik)
5. Modell artefaktok betöltési kísérlete

### 4.2 Gépi tanulási modul (`MLModel.py`)

A `CreditScoringModel` osztály felelős az összes ML művelétért.

**Részletesen lásd:** [5. fejezet](#5-gépi-tanulási-módszertan)

### 4.3 Admin Blueprint (`admin_routes.py`)

Flask Blueprint, amely a `/admin/*` útvonalakat kezeli Jinja2 template renderelésével.

**Szerepkörök és jogosultságok:**

| Szerepkör | Dashboard | Ügyfelek | Hiteligények | Predikciók | Modellek | Felhasználók |
|---|---|---|---|---|---|---|
| `admin` | ✅ | ✅ | ✅ | ✅ | ✅ + élesítés | ✅ |
| `analyst` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| `viewer` | ✅ | olvasás | olvasás | olvasás | olvasás | ❌ |

### 4.4 Adatbázis réteg (`database.py`, `database_models.py`, `db_service.py`)

- **`database.py`**: SQLAlchemy engine, session factory, `init_db()`, `check_db_connection()`
- **`database_models.py`**: ORM modellek (Customer, Prediction, LoanApplication, ModelVersion, AdminUser)
- **`db_service.py`**: Üzleti logika szintű CRUD függvények, statisztikák

### 4.5 Apache Airflow DAG (`airflow/dags/`)

Az Airflow CeleryExecutor módban fut Redis message broker-rel. A `credit_scoring_automl_pipeline` DAG az API `/scoring/train` végpontját hívja meg HTTP POST-tal, biztosítva a rendszeres, ütemezett újratanítást.

### 4.6 MLflow Tracking Server

Külön konténerben fut, PostgreSQL backend store-ral és perzisztens volume-on tárolt artefaktokkal.

**Amit rögzít minden tanítási kísérletről:**
- Tanítási metrikák (accuracy, precision, recall, F1, ROC-AUC) — Champion és Challenger
- Modell artefaktok (pickle fájlok)
- Feature nevek (`feature_names.json`)
- Kísérlet paraméterei

---

## 5. Gépi tanulási módszertan

### 5.1 Shadow System architektúra

A rendszer **Shadow Mode** (árnyékrendszer) módban működik: két modell fut egymás mellett minden predikciónál.

```
Input adatok
     │
     ├──▶ Champion (XGBoost) ──▶ Döntés + PD pontszám  ◀── Éles döntés alapja
     │
     └──▶ Challenger (LightGBM) ──▶ Döntés + PD pontszám  ◀── Összehasonlítás
                │
                ▼
         Egyezés vizsgálat ──▶ Ha eltérnek: figyelmeztetés
```

Az árnyékrendszer előnye: az éles döntést a Champion hozza, de a Challenger eredménye folyamatosan mérhető és összehasonlítható — így modellek cserélhetők anélkül, hogy az éles rendszer kockázata növekedne.

### 5.2 Előfeldolgozás (`preprocessing_pipeline`)

1. **Hiányos értékek kezelése:**
   - Nominális oszlopok: módusz-alapú kitöltés
   - Folytonos oszlopok: medián-alapú kitöltés

2. **Kódolás:**
   - Nominális oszlopok: One-Hot Encoding (scikit-learn `OneHotEncoder`)
   - Ordinális oszlopok: Label Encoding

3. **Normalizáció:**
   - Folytonos oszlopok: Min-Max skálázás (0–1 tartományra)

4. **Objektum típusú oszlopok eltávolítása** (XGBoost kompatibilitáshoz)

5. **Feature nevek mentése** (`feature_names.json`) — biztosítja, hogy az inferencia ugyanolyan struktúrájú bemenetet kapjon, mint a tanítás

### 5.3 Tanítás (`train_shadow_system`)

**Tanítási folyamat:**
1. CSV betöltése és céltváltozó azonosítása (fallback lánc: `target_binary` → `target` → `has_prior_default` → `loan_grade`-ből levezetett)
2. `preprocessing_pipeline()` futtatása
3. Train/test split (80/20, stratified)
4. **Champion (XGBoost)** tanítása:
   - `n_estimators=100`, `max_depth=6`, `learning_rate=0.1`
   - `scale_pos_weight` automatikus osztályegyensúly korrekció
5. **Challenger (LightGBM)** tanítása:
   - `n_estimators=100`, `learning_rate=0.05`
6. Metrikák kiszámítása mindkét modellre
7. Modellek mentése pickle fájlként + MLflow logolás
8. Modellverzió rögzítése az adatbázisban

**Fontos:** `has_prior_default` oszlop kizárva a feature-ök közül (adatszivárgás megelőzés).

### 5.4 Inferencia (`predict_shadow_mode`)

1. Bemeneti adatok normalizálása az elmentett scaler-ekkel
2. Hiányzó feature-ök 0-val való kitöltése (multi-worker kompatibilitás)
3. Champion predikció: osztálycímke + valószínűség
4. Challenger predikció: osztálycímke + valószínűség
5. NLP sentiment analízis a szöveges leírásból
6. Elfogultsági riasztás: ha Champion DEFAULT-ot jelez, de sentiment > 2
7. Eredmény aggregálása és visszaadása

### 5.5 NLP Sentiment Analízis

Kulcsszó-alapú sentiment pontszámítás:

```
sentiment_score = Σ(pozitív kulcsszavak száma) - Σ(negatív kulcsszavak száma)
```

**Pozitív kulcsszavak** (részlet): stabil, erős, kiváló, növekedés, profitabilitás, likviditás  
**Negatív kulcsszavak** (részlet): kockázat, veszteség, késedelem, csőd, felszámolás, inkasszó

### 5.6 Jellemzők (feature-ök)

A rendszer 25 pénzügyi jellemzőt használ a hitelkockázat értékeléséhez, amelyek 5 csoportba sorolhatók.

**Szervezeti adatok (Nominális és Diszkrét)**

| Feature | Magyar neve | Típus |
|---|---|---|
| `Industry_code` | Iparági besorolás | Nominális |
| `legal_entity_type` | Jogi forma (Kft., Zrt. stb.) | Nominális |
| `pl_subseg_desc` | Ügyfélszegmens (Micro/SME/Corporate) | Nominális |
| `address_county` | Székhely megye | Nominális |
| `BusinessAge` | Vállalkozás kora (év) | Diszkrét |
| `num_employees` | Alkalmazottak száma | Diszkrét |
| `LatePaymentCount` | Késedelmes fizetések száma (12 hó) | Diszkrét |

**Mérleg adatok (Folytonos)**

| Feature | Magyar neve | Kockázati irány |
|---|---|---|
| `NetSales` | Nettó árbevétel | ↑ jobb |
| `TotalAssets` | Összes eszköz | ↑ jobb |
| `TotalLiabs` | Összes kötelezettség | ↑ rosszabb |
| `CurrentAssets` | Forgóeszközök | ↑ jobb |
| `CurrentLiabs` | Rövid lejáratú kötelezettségek | ↑ rosszabb |
| `RetainedEarnings` | Eredménytartalék | ↑ jobb |
| `collateral_value` | Fedezet értéke | ↑ jobb |

**Eredménykimutatás (Folytonos)**

| Feature | Magyar neve | Kockázati irány |
|---|---|---|
| `EBIT` | Kamat és adó előtti eredmény | ↑ jobb |
| `GrossMargin` | Bruttó marzs (%) | ↑ jobb |
| `AnnualRevenueGrowth` | Éves árbevétel-növekedés (%) | ↑ jobb |

**Aránymutatók (Folytonos)**

| Feature | Magyar neve | Kockázati irány |
|---|---|---|
| `Operating Margin` | Operatív eredményhányad (%) | ↑ jobb |
| `Return on Assets (ROA)` | Eszközarányos megtérülés (%) | ↑ jobb |
| `Return on Equity (ROE)` | Saját tőke megtérülése (%) | ↑ jobb |
| `Current Ratio` | Likviditási ráta | >1 jobb |
| `QuickRatio` | Gyorslikviditási mutató | >1 jobb |
| `DebtToEquityRatio` | Tőkeáttételi mutató | ↑ rosszabb |
| `WorkingCapital` | Forgótőke (Ft) | ↑ jobb |
| `DaysSalesOutstanding (DSO)` | Vevők átlagos fizetési ideje (nap) | ↑ rosszabb |
| `OperatingCashFlowRatio` | Működési CF ráta | ↑ jobb |

**Dinamikusan számított feature**

| Feature | Forrás | Kockázati irány |
|---|---|---|
| `prior_rejections` | Hiteligény-előzmények DB-ből | ↑ rosszabb |

### 5.7 Modell teljesítmény (referencia értékek)

| Metrika | Champion (XGBoost) | Challenger (LightGBM) |
|---|---|---|
| F1-score | ~0.88 | ~0.85 |
| ROC-AUC | ~0.99 | ~0.98 |
| Accuracy | ~0.90 | ~0.88 |

> ⚠️ Az értékek szintetikus adaton mért tájékoztató értékek. Valós adaton az eredmények eltérhetnek.

---

## 6. Adatbázis-séma

### 6.1 `customers` tábla

| Oszlop | Típus | Leírás |
|---|---|---|
| `id` | UUID (PK) | Egyedi azonosító |
| `name` | VARCHAR(255) | Ügyfél/cég neve |
| `email` | VARCHAR(255) | Email cím |
| `industry_code` | VARCHAR(100) | Iparági besorolás |
| `legal_entity_type` | VARCHAR(100) | Jogi forma |
| `client_segment` | VARCHAR(100) | Ügyfélszegmens (Micro/SME/Corporate) |
| `address_county` | VARCHAR(100) | Székhely megye |
| `business_age` | INTEGER | Vállalkozás kora (év) |
| `num_employees` | INTEGER | Alkalmazottak száma |
| `net_sales` | FLOAT | Nettó árbevétel (Ft) |
| `total_assets` | FLOAT | Összes eszköz (Ft) |
| `total_liabs` | FLOAT | Összes kötelezettség (Ft) |
| `current_assets` | FLOAT | Forgóeszközök (Ft) |
| `current_liabs` | FLOAT | Rövid lejáratú kötelezettségek (Ft) |
| `retained_earnings` | FLOAT | Eredménytartalék (Ft) |
| `collateral_value` | FLOAT | Fedezet becsült értéke (Ft) |
| `ebit` | FLOAT | Kamat és adó előtti eredmény (Ft) |
| `gross_margin` | FLOAT | Bruttó marzs (%) |
| `annual_revenue_growth` | FLOAT | Éves árbevétel-növekedés (%) |
| `operating_margin` | FLOAT | Operatív eredményhányad (%) |
| `return_on_assets` | FLOAT | Eszközarányos megtérülés / ROA (%) |
| `return_on_equity` | FLOAT | Saját tőke megtérülése / ROE (%) |
| `current_ratio` | FLOAT | Likviditási ráta |
| `quick_ratio` | FLOAT | Gyorslikviditási mutató |
| `debt_to_equity` | FLOAT | Tőkeáttételi mutató |
| `working_capital` | FLOAT | Forgótőke (Ft) |
| `days_sales_outstanding` | FLOAT | Vevők átl. fizetési ideje / DSO (nap) |
| `operating_cash_flow_ratio` | FLOAT | Működési CF / Rövid lej. köt. |
| `late_payment_count` | INTEGER | Késedelmes fizetések száma (12 hó) |
| `description` | TEXT | Szöveges leírás (NLP elemzéshez) |
| `created_at` | DATETIME | Felvétel időpontja |

### 6.2 `predictions` tábla

| Oszlop | Típus | Leírás |
|---|---|---|
| `id` | UUID (PK) | Egyedi azonosító |
| `customer_id` | UUID (FK) | Kapcsolt ügyfél |
| `model_version` | VARCHAR | Modellverzió azonosítója |
| `mlflow_run_id` | VARCHAR | MLflow kísérlet run ID |
| `prediction` | INTEGER | Döntés: 0=alacsony, 1=magas kockázat |
| `prediction_label` | VARCHAR | "NON-DEFAULT" / "DEFAULT" |
| `probability_of_default` | FLOAT | PD valószínűség (0–1) |
| `challenger_prediction` | INTEGER | Challenger döntés |
| `challenger_probability` | FLOAT | Challenger PD |
| `models_agree` | BOOLEAN | Champion és Challenger egyezik? |
| `sentiment_score` | FLOAT | NLP sentiment pontszám |
| `bias_detected` | BOOLEAN | Elfogultsági riasztás |
| `input_data` | JSON | Bemeneti adatok snapshot-ja |
| `created_at` | DATETIME | Predikció időpontja |

### 6.3 `loan_applications` tábla

| Oszlop | Típus | Leírás |
|---|---|---|
| `id` | UUID (PK) | Egyedi azonosító |
| `customer_id` | UUID (FK) | Kapcsolt ügyfél |
| `prediction_id` | UUID (FK) | Kapcsolt kreditbírálat |
| `requested_amount` | FLOAT | Igényelt hitelösszeg (Ft) |
| `loan_purpose` | VARCHAR(255) | Hitelcél |
| `loan_term_months` | INTEGER | Futamidő (hónap) |
| `notes` | TEXT | Kérelmező megjegyzése |
| `status` | VARCHAR(50) | Státusz (lásd workflow) |
| `decision_notes` | TEXT | Döntéshozói indoklás |
| `decided_by` | VARCHAR | Döntéshozó felhasználóneve |
| `decided_at` | DATETIME | Döntés időpontja |
| `prior_rejections` | INTEGER | Korábbi elutasítások száma (scoring időpontjában) |
| `created_at` | DATETIME | Benyújtás időpontja |

### 6.4 `model_versions` tábla

| Oszlop | Típus | Leírás |
|---|---|---|
| `id` | UUID (PK) | Egyedi azonosító |
| `model_name` | VARCHAR | Modell neve |
| `version` | VARCHAR | Verziószám |
| `mlflow_run_id` | VARCHAR | MLflow run azonosító |
| `champion_f1` | FLOAT | Champion F1-score |
| `champion_roc_auc` | FLOAT | Champion ROC-AUC |
| `challenger_f1` | FLOAT | Challenger F1-score |
| `status` | VARCHAR | staging / production / archived |
| `created_at` | DATETIME | Tanítás időpontja |

### 6.5 `admin_users` tábla

| Oszlop | Típus | Leírás |
|---|---|---|
| `id` | UUID (PK) | Egyedi azonosító |
| `username` | VARCHAR (unique) | Felhasználónév |
| `password_hash` | VARCHAR | Werkzeug PBKDF2 hash |
| `role` | VARCHAR | admin / analyst / viewer |
| `is_active` | BOOLEAN | Fiók aktív? |
| `last_login` | DATETIME | Utolsó bejelentkezés |

---

## 7. REST API dokumentáció

Az interaktív Swagger UI elérhető: **http://localhost:8080/swagger**

### 7.1 Scoring végpontok

#### `POST /scoring/train`
Modell betanítása feltöltött CSV fájlból.

**Request:** `multipart/form-data`, `file` mező (CSV)

**Response:**
```json
{
  "status": "success",
  "champion": { "accuracy": 0.91, "f1_score": 0.88, "roc_auc": 0.99 },
  "challenger": { "accuracy": 0.89, "f1_score": 0.85, "roc_auc": 0.98 },
  "mlflow_run_id": "abc123...",
  "model_version_id": "uuid..."
}
```

#### `POST /scoring/predict`
Hitelkockázat becslése ügyféladatok alapján.

**Request:**
```json
{
  "application_data": {
    "NetSales": 50000000,
    "Operating Margin": 12.5,
    "Current Ratio": 1.8,
    "DebtToEquityRatio": 1.2,
    "Return on Assets (ROA)": 6.0,
    "LatePaymentCount": 0,
    "description": "Stabil cég, növekvő árbevétel."
  },
  "customer_id": "uuid-opcionális"
}
```

**Response:**
```json
{
  "prediction": 0,
  "prediction_label": "NON-DEFAULT",
  "pd_score": 0.12,
  "shadow_meta": {
    "challenger_prediction": 0,
    "challenger_pd": 0.14,
    "agreement": true,
    "sentiment_score": 2,
    "bias_detected": false
  }
}
```

#### `POST /scoring/trigger-training`
Airflow DAG indítása — a tanítás Airflow workeren fut le.

**Response:**
```json
{
  "state": "queued",
  "dag_run_id": "manual__2024-01-01T10:00:00+00:00"
}
```

#### `GET /scoring/training-status/{dag_run_id}`
Futó tanítási DAG állapotának lekérdezése.

### 7.2 Ügyfél végpontok

#### `POST /api/customers` — Ügyfél létrehozása
#### `GET /api/customers` — Ügyfelek listája
#### `GET /api/customers/{id}` — Ügyfél adatai
#### `GET /api/customers/{id}/predictions` — Ügyfél predikciói
#### `DELETE /api/customers/{id}` — Ügyfél törlése

### 7.3 Predikció végpontok

#### `GET /api/predictions` — Összes predikció
#### `GET /api/predictions/stats` — Összesített statisztikák

**Response példa:**
```json
{
  "total": 142,
  "defaults": 28,
  "non_defaults": 114,
  "default_rate": 0.197,
  "bias_detections": 3
}
```

---

## 8. Admin felület

Az admin felület elérhető: **http://localhost:8080/admin**

### 8.1 Dashboard (`/admin/dashboard`)

A vezérlőpult egyetlen oldalon összesíti a rendszer állapotát:

**KPI kártyák (felső sor):**
- Nyilvántartott ügyfelek száma
- Elvégzett hitelminősítések száma
- Nemfizetési kockázat aránya (magas kockázatú minősítések %-ban)
- Elfogultsági riasztások száma (modell vs. szöveg eltérés)

**Hiteligény állapotsor:** Várakozó / Gépi minősítés kész / Jóváhagyott / Elutasított / Kézi elbírálás alatt értékek

**Diagramok (Chart.js):**
- Fánkdiagram: hitelminősítési eredmény megoszlása (alacsony vs. magas kockázat)
- Fánkdiagram: hiteligények állapot-megoszlása (5 státusz)
- Vízszintes sávdiagram: éles modell teljesítménye (Champion F1, Champion AUC, Challenger F1)

**Táblázatok:**
- Legutóbbi 10 hitelminősítés (nemfizetési valószínűség progress barral, elfogultsági riasztással)
- Éles modell adatlap (tooltippel magyarázott F1, AUC értékek)
- Legutóbb felvett 5 ügyfél

### 8.2 Ügyfélkezelés (`/admin/customers`)

- Ügyfélkeresés névben és emailben
- Új ügyfél létrehozása részletes pénzügyi adatlappal (tooltipekkel)
- Ügyfél adatlap: összes tárolt pénzügyi mutató, predikciós előzmények táblázata
- Közvetlen predikció futtatás az ügyfél adataiból
- Hiteligény benyújtása az ügyféltől
- Ügyfél törlése (csak admin szerepkörrel)

### 8.3 Hiteligény kezelés (`/admin/loan-applications`)

**Részletes leírás:** [9. fejezet](#9-hiteligény-workflow)

### 8.4 Predikciók (`/admin/predictions`)

- Teljes predikciós előzmények szűrhető listája
- Minden sor tartalmazza: kockázati besorolás, nemfizetési valószínűség %, másodlagos modell, szöveg hangulata, elfogultsági jelzés
- Részletes view: teljes input snapshot JSON-ban, MLflow run link

### 8.5 Modellverziók (`/admin/models`)

- Verziólista metrikákkal (Champion F1, AUC; Challenger F1, AUC)
- Staging → Production élesítés gombbal (automatikusan archiválja az előző production verziót)

---

## 9. Hiteligény workflow

### 9.1 Állapotátmenetek

```
        benyújtás
           │
           ▼
      ┌─────────┐
      │ pending │ ──── kreditbírálat indítása ────▶ ┌────────┐
      └─────────┘                                    │ scored │
                                                     └───┬────┘
                                              ┌──────────┼──────────┐
                                              ▼          ▼          ▼
                                        ┌──────────┐ ┌──────────┐ ┌───────────────┐
                                        │ approved │ │ rejected │ │ manual_review │
                                        └──────────┘ └──────────┘ └───────┬───────┘
                                                                           │
                                                              ┌────────────┼────────────┐
                                                              ▼                         ▼
                                                        ┌──────────┐            ┌──────────┐
                                                        │ approved │            │ rejected │
                                                        └──────────┘            └──────────┘
```

| Státusz | Magyar neve | Leírás |
|---|---|---|
| `pending` | Függőben | Benyújtva, kreditbírálat még nem futott |
| `scored` | Kreditbírálat kész | Modell lefutott, döntés vár |
| `approved` | Jóváhagyva | Hitel jóváhagyva |
| `rejected` | Elutasítva | Hitel elutasítva |
| `manual_review` | Kézi elbírálás | Emberi felülvizsgálat szükséges |

### 9.2 Prior rejections feature

A `prior_rejections` (korábbi elutasítások) automatikusan kerül kiszámításra és átadásra a modellnek a kreditbírálat futtatásakor:

```python
prior_rejections = count(loan_applications WHERE customer_id = X AND status = 'rejected')
```

Ez a feature lehetővé teszi, hogy az ismételt hiteligénylők esetén a modell figyelembe vegye a korábbi elutasítások számát — ami reális kockázatjelző.

### 9.3 Auditnapló

Minden döntésnél rögzítésre kerül:
- Döntéshozó felhasználóneve (`decided_by`)
- Döntés időpontja (`decided_at`)
- Döntéshozói indoklás (`decision_notes`)
- A scoring pillanatában fennálló `prior_rejections` érték

---

## 10. Konténerizáció és üzembe helyezés

### 10.1 Docker Swarm topológia

```
docker stack: credit_scoring
│
├── credit_scoring_api (2 replika, load balanced)
├── credit_scoring_mlflow (1 replika)
├── credit_scoring_postgres_db (1 replika, manager node)
├── credit_scoring_postgres_airflow (1 replika)
├── credit_scoring_redis (1 replika)
├── credit_scoring_airflow_init (egyszeri futás)
├── credit_scoring_airflow_webserver (1 replika)
├── credit_scoring_airflow_scheduler (1 replika)
└── credit_scoring_airflow_worker (1 replika)
```

### 10.2 Docker volume-ok

| Volume | Tartalom | Perzisztencia |
|---|---|---|
| `postgres_data` | App adatbázis adatai | Perzisztens |
| `postgres_airflow_data` | Airflow adatbázis | Perzisztens |
| `mlflow_artifacts` | MLflow modell artefaktok | Perzisztens |
| `airflow_logs` | Airflow futtatási logok | Perzisztens |
| `model_artifacts` | Champion/Challenger pickle fájlok, feature_names.json | Perzisztens |

### 10.3 Rolling update stratégia

Az API service `start-first` update stratégiával van konfigurálva:
- Új replika elindul → health check sikerül → régi replika leáll
- Zero-downtime deployment biztosított

```yaml
update_config:
  parallelism: 1
  delay: 10s
  order: start-first
```

### 10.4 Skálázhatóság

Az API service horizontálisan skálázható:

```powershell
docker service scale credit_scoring_api=3
```

A multi-worker Gunicorn konfiguráció és a `model_artifacts` megosztott volume biztosítja, hogy minden worker replika ugyanazt a modellt használja.

---

## 11. Biztonság és hozzáférés-kezelés

### 11.1 Jelszókezelés

- Admin jelszavak: **Werkzeug PBKDF2** hash (nem plain text)
- Session kezelés: Flask server-side session, `SECRET_KEY` alapján

### 11.2 Airflow REST API

Az Airflow webserver `basic_auth + session` autentikációval van konfigurálva:
```
AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth,airflow.api.auth.backend.session
```

### 11.3 Role-based access control (Admin UI)

| Művelet | admin | analyst | viewer |
|---|---|---|---|
| Ügyfél törlése | ✅ | ❌ | ❌ |
| Modell élesítése | ✅ | ❌ | ❌ |
| Felhasználó létrehozása | ✅ | ❌ | ❌ |
| Hiteligény döntés | ✅ | ✅ | ❌ |
| Kreditbírálat futtatása | ✅ | ✅ | ❌ |

### 11.4 Javasolt éles konfigurációk

- [ ] `SECRET_KEY` csere véletlenszerű, erős értékre
- [ ] `ADMIN_PASSWORD` csere
- [ ] `POSTGRES_PASSWORD` csere
- [ ] HTTPS proxy (pl. Nginx reverse proxy) az API elé
- [ ] Airflow Fernet key beállítása

---

## 12. Minőségbiztosítás és monitoring

### 12.1 Health check végpontok

| Végpont | Leírás |
|---|---|
| `GET /health` | API + DB kapcsolat állapota |
| `http://mlflow:5102/health` | MLflow szerver állapota |
| `http://airflow_webserver:8080/health` | Airflow állapota |

### 12.2 MLflow kísérletkövetés

Minden tanítási futtatáshoz rögzített adatok:
- **Metrikák:** accuracy, precision, recall, F1, ROC-AUC (Champion és Challenger)
- **Artefaktok:** modell pickle fájlok, feature_names.json
- **Paraméterek:** model típus, tanítási adatok mérete

### 12.3 Elfogultsági (Bias) monitoring

A rendszer automatikusan jelzi, ha:
- A Champion modell **magas kockázatot** (DEFAULT) jelez, DE
- A szöveges leírás sentiment pontszáma **pozitív (>2)**

Ez a kombináció arra utalhat, hogy az elemző szöveges értékelése és a kvantitatív modell ellentmond egymásnak — emberi felülvizsgálatot igényelhet.

### 12.4 Shadow System monitoring

A `models_agree` mező és a Predikciók listában az "Eltérés" jelzés lehetővé teszi:
- A Champion és Challenger eltérési arányának figyelését
- Ha az eltérési arány nő, az a modell drift jele lehet
- Alapja a Champion → Challenger csere döntéshozatalának

---

*Dokumentáció vége. A rendszer forráskódja és telepítési útmutatója az INSTALL.md fájlban található.*
