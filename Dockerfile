# ============================================================
# Credit Scoring API - Dockerfile
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# Rendszer-függőségek (psycopg2-binary + libgomp lightgbm-hez)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python csomagok
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Alkalmazás fájlok
COPY . .

# Artifact és adatkönyvtárak
RUN mkdir -p artifacts/models artifacts/encoders artifacts/nan_outlier_handler data logs

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
