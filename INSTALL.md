# Credit Scoring System — Telepítési Útmutató

## Előfeltételek

| Szoftver | Verzió | Megjegyzés |
|---|---|---|
| Docker Desktop | 4.x+ | Docker Swarm módban kell futnia |
| Python | 3.11+ | Csak lokális fejlesztéshez szükséges |
| Git | bármely | Forráskód letöltéséhez |

---

## 1. Gyors indítás (Docker Swarm)

```powershell
# 1. Swarm inicializáció (ha még nem fut)
docker swarm init

# 2. .env fájl előkészítése
copy .env.example .env
# Szerkeszd meg a .env fájlt a kívánt jelszavakkal!

# 3. API image build
docker build -t credit_scoring_api:latest .

# 4. Stack deploy
docker stack deploy -c docker-compose.yml credit_scoring

# 5. Státusz ellenőrzés (várj ~60 másodpercet az indulásig)
docker stack services credit_scoring
```

A rendszer indulása **~2-3 percet** vesz igénybe, amíg az összes szolgáltatás (PostgreSQL, Redis, Airflow, MLflow, API) el nem indul.

---

## 2. Szolgáltatások és portok

| Szolgáltatás | URL | Leírás |
|---|---|---|
| **API + Admin felület** | http://localhost:8080 | Fő REST API, Admin UI, Swagger |
| **Swagger UI** | http://localhost:8080/swagger | Interaktív API dokumentáció |
| **Admin felület** | http://localhost:8080/admin | Webes adminisztrációs felület |
| **MLflow UI** | http://localhost:5102 | Modell tracking és kísérletkövetés |
| **Airflow UI** | http://localhost:8793 | DAG-alapú pipeline ütemezés |

---

## 3. Bejelentkezési adatok

| Rendszer | Felhasználó | Jelszó | Módosítás |
|---|---|---|---|
| Admin UI | `admin` | `Admin1234!` | `ADMIN_PASSWORD` env var |
| Airflow | `airflow` | `airflow` | `_AIRFLOW_WWW_USER_PASSWORD` env var |
| PostgreSQL (app DB) | `credit_user` | `credit_pass` | `POSTGRES_PASSWORD` env var |

> ⚠️ **FONTOS:** Éles telepítés előtt minden jelszót változtass meg a `.env` fájlban!

---

## 4. Környezeti változók (`.env`)

```dotenv
# Adatbázis
POSTGRES_USER=credit_user
POSTGRES_PASSWORD=credit_pass
POSTGRES_DB=credit_scoring_db

# Flask
SECRET_KEY=change_me_in_production
ADMIN_PASSWORD=Admin1234!

# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5102

# Airflow REST API elérés (API → Airflow kommunikációhoz)
AIRFLOW_BASE_URL=http://airflow_webserver:8080
AIRFLOW_USER=airflow
AIRFLOW_PASSWORD=airflow

# Skálázás
REPLICAS_API=2
REPLICAS_MLFLOW=1
```

---

## 5. Modell betanítása

### A) Swagger UI-n keresztül (ajánlott)
1. Nyisd meg: http://localhost:8080/swagger
2. `POST /scoring/train` → CSV fájl feltöltése
3. Az eredmény megjelenik az MLflow UI-ban (http://localhost:5102)

### B) Airflow DAG indítása (ütemezett futtatás)
1. Nyisd meg: http://localhost:8793
2. DAG neve: `credit_scoring_automl_pipeline`
3. Kattints a ▶ (Trigger DAG) gombra

### C) REST API-n keresztül
```bash
# Tanítás CSV feltöltéssel
curl -X POST http://localhost:8080/scoring/train \
  -F "file=@data/processed_credit_data.csv"

# Tanítás Airflow DAG-on keresztül (a DAG hívja meg az API-t)
curl -X POST http://localhost:8080/scoring/trigger-training
```

---

## 6. Hiteligény workflow — lépések

```
1. Ügyfél létrehozása  →  Admin / Ügyfelek / Új ügyfél
2. Hiteligény benyújtása  →  Admin / Hiteligények / Új hiteligény
3. Kreditbírálat indítása  →  Hiteligény részletei / Kreditbírálat indítása
4. Döntés meghozatala  →  Jóváhagyás / Elutasítás / Kézi elbírálás
```

---

## 7. API végpontok áttekintése

| Metódus | Végpont | Leírás |
|---|---|---|
| `POST` | `/scoring/train` | Modell tanítása CSV fájlból |
| `POST` | `/scoring/predict` | Hitelkockázat becslése |
| `POST` | `/scoring/trigger-training` | Airflow DAG indítása |
| `GET` | `/scoring/training-status/{dag_run_id}` | DAG futás állapota |
| `POST` | `/api/customers` | Ügyfél létrehozása |
| `GET` | `/api/customers` | Ügyfelek listája |
| `GET` | `/api/customers/{id}` | Ügyfél adatai |
| `GET` | `/api/customers/{id}/predictions` | Ügyfél predikciói |
| `GET` | `/api/predictions` | Összes predikció |
| `GET` | `/api/predictions/stats` | Összesített statisztikák |
| `GET` | `/health` | Rendszer állapot |

---

## 8. Adatbázis séma

| Tábla | Leírás |
|---|---|
| `customers` | Ügyfelek azonosítói és pénzügyi mutatói |
| `predictions` | Kreditbírálati eredmények (Champion + Challenger + NLP) |
| `loan_applications` | Hiteligények, státuszkövetés, döntések |
| `model_versions` | Modellverziók metrikákkal (F1, AUC, státusz) |
| `admin_users` | Admin felhasználók és szerepkörök |

---

## 9. Admin felület funkciók

| Menüpont | Elérhető funkciók |
|---|---|
| **Dashboard** | Összesített statisztikák, kockázati arány, elfogultsági jelzések |
| **Ügyfelek** | Létrehozás, keresés, részletes adatlap, predikciós előzmények |
| **Hiteligények** | Benyújtás, kreditbírálat futtatása, döntés rögzítése, státuszkövetés |
| **Predikciók** | Teljes előzménylista, részletes view (input snapshot, shadow metadata) |
| **Modellverziók** | Verziólista, production élesítés |
| **Felhasználók** | (csak admin) Új felhasználók, szerepkörök (admin / analyst / viewer) |

---

## 10. Docker Swarm kezelés

```powershell
# API replika szám növelése (skálázás)
docker service scale credit_scoring_api=3

# Stack frissítése (új image build után)
docker build -t credit_scoring_api:latest .
docker service update --force credit_scoring_api

# Teljes stack újratelepítése
docker stack deploy -c docker-compose.yml credit_scoring

# Stack leállítása (adatok megmaradnak a volume-okban)
docker stack rm credit_scoring

# Összes adat törlése (volume-ok is)
docker stack rm credit_scoring
docker volume rm credit_scoring_postgres_data credit_scoring_model_artifacts credit_scoring_mlflow_artifacts
```

---

## 11. Hibaelhárítás

### Szolgáltatás nem indul el
```powershell
# Részletes státusz
docker service ps credit_scoring_api --no-trunc

# Konténer logok
docker logs <container_id> 2>&1 | Select-Object -Last 50
```

### Modell nem töltődik be (első indulás)
Az első indulás után a modellt be kell tanítani:
1. `POST /scoring/train` CSV fájllal, vagy
2. Airflow DAG manuális indítása

### Adatbázis kapcsolat hiba
```powershell
# PostgreSQL konténer állapota
docker service ps credit_scoring_postgres_db

# Health check
curl http://localhost:8080/health
```
