param(
    [Parameter(Mandatory=$true)][int]$YearFrom,
    [Parameter(Mandatory=$true)][int]$YearTo
)
$ErrorActionPreference = "Stop"
& .\.venv\Scripts\Activate.ps1
python -m src.cli test-connection
python -m src.cli ingest-oracle-views --year-from $YearFrom --year-to $YearTo
python -m streamlit run src\dashboard\app.py
