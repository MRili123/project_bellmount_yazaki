@echo off
REM Launch the Bellmounth machine app with Python 3.11 (the interpreter that
REM has TensorFlow installed). The default "python" on this PC is 3.15, which
REM does NOT have TensorFlow, so AUTO capture / the mesure model won't work there.

cd /d C:\BellmouthProject\app
py -3.11 app.py

echo.
echo App closed. Press any key to exit...
pause
