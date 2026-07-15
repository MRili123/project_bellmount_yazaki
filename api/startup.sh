#!/bin/bash
# Azure App Service (Linux, Python) startup command.
# Set this as the "Startup Command" in the App Service:
#   Configuration -> General settings -> Startup Command
#
# Runs the FastAPI app (main.py -> `app`) under gunicorn with uvicorn workers.
gunicorn main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 \
    --bind 0.0.0.0:8000 \
    --timeout 600
