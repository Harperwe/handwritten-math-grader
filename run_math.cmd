@echo off
setlocal
set "COMER_PYTHON=%~dp0..\..\work\env-comer\python.exe"
if not exist "%COMER_PYTHON%" (
  echo CoMER Python environment not found. Use the Python commands in the usage guide.
  exit /b 2
)
if "%~1"=="" (
  "%COMER_PYTHON%" "%~dp0recognize_math.py" --image "%~dp0example\arithmetic_samples\UN_128_em_1003.bmp" --output "%~dp0repro_outputs\latest.json"
) else (
  "%COMER_PYTHON%" "%~dp0recognize_math.py" %*
)
exit /b %errorlevel%
