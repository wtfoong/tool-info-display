# Set current working directory = script directory
cd "$PSScriptRoot"

# Activate virtual environment
. ".venv\Scripts\Activate.ps1"

# run BackEndJobCalculateLowestCPk python script
python ".\BackEndJobCalculateLowestCPk.py"

# for manual run, in powershell, cd to this dir, then ".\backend_launcher.ps1"