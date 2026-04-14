#!/bin/bash
set -e

echo "=== Beyond Madeira CRM API v2.0 ==="
echo "[INIT] Running database migrations..."
python -m flask db upgrade

echo "[INIT] Checking if initial sync needed..."
RECORD_COUNT=$(python -c "
from app import create_app
from app.models.reservas import RentCar
a = create_app()
with a.app_context():
    print(RentCar.query.count())
" 2>/dev/null || echo "0")

if [ "$RECORD_COUNT" = "0" ]; then
    echo "[INIT] Empty database — starting sync in background..."
    python -m flask sync-initial &
else
    echo "[INIT] Database has $RECORD_COUNT RC records — skipping initial sync."
fi

echo "[INIT] Starting gunicorn..."
exec gunicorn main:app \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --threads 8 \
    --worker-class gthread \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile -
