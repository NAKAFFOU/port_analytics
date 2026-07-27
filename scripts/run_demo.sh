#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
python -m src.cli run-demo
streamlit run src/dashboard/app.py --server.address 0.0.0.0 --server.port 8501
