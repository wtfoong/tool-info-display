# Set current working directory = script directory
cd "$PSScriptRoot"

# Activate virtual environment
. ".venv\Scripts\Activate.ps1"

# starting server
streamlit run app.py

# for manual run, in powershell, cd to this dir, then ".\app_launcher.ps1"