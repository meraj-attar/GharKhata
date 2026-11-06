#!/usr/bin/env bash
# Render native build. Node/npm must be available for the Vite build.
set -euo pipefail
python -m pip install -r backend/requirements.txt
cd frontend
npm install --no-audit --no-fund
npm run build
