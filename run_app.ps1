$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:HOME = $projectRoot
$env:USERPROFILE = $projectRoot

python -m streamlit run app.py --server.port 8501 --server.headless true
