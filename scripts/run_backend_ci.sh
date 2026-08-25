#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export DATABASE_URL="${DATABASE_URL:-sqlite:///./risk_adjustment.db}"

python -m pip install --upgrade pip
pip install -r requirements.txt
python -m alembic upgrade head
python -m unittest discover -s backend/tests -p "test_*.py" -v
