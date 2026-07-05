@echo off
REM Train Model Script - No GUI, Just Results!

echo.
echo ================================================================================
echo CABLE MEASUREMENT MODEL TRAINING
echo ================================================================================
echo.

cd /d C:\BellmouthProject\app
py -3.11 train_model.py

echo.
echo ================================================================================
echo Done! Press any key to exit...
echo ================================================================================
pause
