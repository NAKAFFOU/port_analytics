#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip sqlite3
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp -n .env.example .env || true
printf '\nInstallation complete. Edit .env, then run:\n'
printf '  source .venv/bin/activate\n'
printf '  python -m src.cli run-demo\n'
printf '  streamlit run src/dashboard/app.py --server.address 0.0.0.0 --server.port 8501\n'
