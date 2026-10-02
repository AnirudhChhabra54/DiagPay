#!/bin/sh
set -e

echo "=== DiagPay Backend Startup ==="

# Wait for PostgreSQL to become fully available
echo "Waiting for PostgreSQL..."
while ! nc -z ${DB_HOST:-postgres} ${DB_PORT:-5432}; do
  sleep 0.5
done
echo "PostgreSQL is ready!"

# Wait for Redis to become available if enabled
if [ "${REDIS_ENABLED:-true}" = "true" ]; then
  echo "Waiting for Redis..."
  while ! nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379}; do
    sleep 0.5
  done
  echo "Redis is ready!"
fi

# Apply Alembic database migrations
echo "Applying database migrations..."
alembic upgrade head
echo "Migrations applied successfully!"

# Seed database with initial demo data
echo "Seeding initial data..."
python -m app.scripts.seed
echo "Database seeded successfully!"

# Start FastAPI application with Uvicorn
echo "Starting Uvicorn server on 0.0.0.0:8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
