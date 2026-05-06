#!/bin/bash
# ============================================================
# Credit Scoring API - Docker entrypoint
# Megvárja a PostgreSQL-t, majd inicializálja a DB-t és elindítja az API-t.
# ============================================================
set -e

echo "Varakozas a PostgreSQL-re..."
until python -c "
import sqlalchemy, os
engine = sqlalchemy.create_engine(os.environ['DATABASE_URL'])
with engine.connect() as c:
    c.execute(sqlalchemy.text('SELECT 1'))
print('DB kesz')
" 2>/dev/null; do
    echo "   PostgreSQL meg nem elerheto, ujra 3s mulva..."
    sleep 3
done

echo "PostgreSQL elerheto!"
echo "Adatbazis inicializacio..."
python -c "from database import init_db; init_db()"

echo "Admin felhasznalo bootstrap..."
python -c "
from database import SessionLocal
import db_service
from werkzeug.security import generate_password_hash
import os
db = SessionLocal()
try:
    if not db_service.get_admin_user_by_username(db, 'admin'):
        pw = generate_password_hash(os.getenv('ADMIN_PASSWORD', 'Admin1234!'))
        db_service.create_admin_user(db, 'admin', pw, role='admin')
        print('Admin felhasznalo letrehozva.')
    else:
        print('Admin felhasznalo mar letezik.')
finally:
    db.close()
"

echo "Credit Scoring API inditasa..."
exec gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 120 --access-logfile - app:app
