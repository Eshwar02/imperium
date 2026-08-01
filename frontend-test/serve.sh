#!/usr/bin/env bash
# Simple test console for the whole Imperium backend — single static HTML, no build.
# Must run on port 5173 (the backend's allowed CORS origin).
# Backend must be running separately:
#   cd backend && .venv/bin/uvicorn imperium.main:app --reload --port 8000
cd "$(dirname "$0")"
echo "Test console → http://localhost:5173   (backend expected at http://localhost:8000)"
exec python -m http.server 5173
