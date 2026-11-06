
#!/usr/bin/env bash
# Render native build. Node/npm must be available for the Vite build.
set -euo pipefail

python -m pip install -r backend/requirements.txt

# Apply database migrations to the configured Neon staging database.
cd backend
alembic upgrade head
cd ..

# Build the React frontend.
cd frontend
npm ci --no-audit --no-fund
npm run build
