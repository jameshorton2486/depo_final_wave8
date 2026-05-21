@echo off
setlocal
set PYTHON_BIN=.\.venv\Scripts\python.exe

echo [1/5] Verifying imports...
%PYTHON_BIN% -c "import backend.app; import backend.database.init_db; import desktop.launcher"
if errorlevel 1 exit /b 1

echo [2/5] Verifying SQLite initialization...
%PYTHON_BIN% -c "from backend.database.init_db import initialize_database; path = initialize_database(); print(path)"
if errorlevel 1 exit /b 1

echo [3/5] Verifying frontend files...
%PYTHON_BIN% -c "from pathlib import Path; required = [Path('frontend/index.html'), Path('frontend/screens/stage_1_intake.html'), Path('frontend/screens/stage_6_export.html')]; missing = [str(path) for path in required if not path.exists()]; assert not missing, missing"
if errorlevel 1 exit /b 1

echo [4/5] Verifying FastAPI startup...
%PYTHON_BIN% -c "import json, subprocess, time, urllib.request; process = subprocess.Popen(['.\\\\.venv\\\\Scripts\\\\python.exe', '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', '8765']); time.sleep(2); health = json.loads(urllib.request.urlopen('http://127.0.0.1:8765/api/health').read().decode('utf-8')); frontend = urllib.request.urlopen('http://127.0.0.1:8765/').status; process.terminate(); process.wait(timeout=10); assert health['status'] == 'ok'; assert frontend == 200; print(health)"
if errorlevel 1 exit /b 1

echo [5/5] Verifying desktop launcher wiring...
%PYTHON_BIN% -c "import os; os.environ['DEPOPRO_LAUNCHER_SMOKE_TEST'] = '1'; import desktop.launcher as launcher; launcher.main(); print('launcher ok')"
if errorlevel 1 exit /b 1

echo Verification passed.
