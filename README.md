# Credit Scoring System

Vállalati hitelkockázat-értékelő rendszer gépi tanulás alapon. Két modell párhuzamos futtatásával (Shadow System), NLP sentiment elemzéssel és teljes hiteligénylési workflow-val.

## Technológiák

| Komponens | Technológia |
|---|---|
| API | Flask + Flask-RESTX (Swagger) |
| Champion modell | XGBoost |
| Challenger modell | LightGBM |
| Kísérletkövetés | MLflow |
| Pipeline ütemezés | Apache Airflow |
| Adatbázis | PostgreSQL 16 |
| Konténerizáció | Docker Swarm |

## Gyors indítás

```powershell
# Swarm inicializáció (ha még nem fut)
docker swarm init

# .env fájl előkészítése
copy .env.example .env

# Image build és stack deploy
docker build -t credit_scoring_api:latest .
docker stack deploy -c docker-compose.yml credit_scoring
```

Az indulás ~2-3 percet vesz igénybe.

## Szolgáltatások

| Szolgáltatás | URL |
|---|---|
| API + Admin felület | http://localhost:8080 |
| Swagger UI | http://localhost:8080/swagger |
| MLflow UI | http://localhost:5102 |
| Airflow UI | http://localhost:8793 |

## Bejelentkezés

| Rendszer | Felhasználó | Jelszó |
|---|---|---|
| Admin UI | `admin` | `Admin1234!` |
| Airflow | `airflow` | `airflow` |

> ⚠️ Éles telepítés előtt minden jelszót változtass meg a `.env` fájlban!

## Modell betanítása

```bash
# CSV feltöltéssel (REST API)
curl -X POST http://localhost:8080/scoring/train \
  -F "file=@data/processed_credit_data.csv"
```

Vagy Swagger UI-n keresztül: `POST /scoring/train`

## Főbb API végpontok

| Metódus | Végpont | Leírás |
|---|---|---|
| `POST` | `/scoring/train` | Modell tanítása CSV fájlból |
| `POST` | `/scoring/predict` | Hitelkockázat becslése |
| `POST` | `/scoring/trigger-training` | Airflow DAG indítása |
| `GET` | `/api/customers` | Ügyfelek listája |
| `GET` | `/api/predictions/stats` | Összesített statisztikák |
| `GET` | `/health` | Rendszer állapot |

## Hiteligény workflow

```
Ügyfél létrehozása → Hiteligény benyújtása → Kreditbírálat futtatása → Döntés
     (pending)              (pending)               (scored)          (approved / rejected / manual_review)
```

## Szerepkörök

| Művelet | admin | analyst | viewer |
|---|---|---|---|
| Ügyfél törlése | ✅ | ❌ | ❌ |
| Modell élesítése | ✅ | ❌ | ❌ |
| Hiteligény döntés | ✅ | ✅ | ❌ |
| Kreditbírálat futtatása | ✅ | ✅ | ❌ |
| Adatok megtekintése | ✅ | ✅ | ✅ |

## Részletes dokumentáció

- Telepítési útmutató: [INSTALL.md](INSTALL.md)
- Technikai dokumentáció: [DOCUMENTATION.md](DOCUMENTATION.md)
