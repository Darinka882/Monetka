#!/bin/bash
pip install -r requirements.txt
exec gunicorn bot:app --worker-class aiohttp.GunicornWebWorker --bind 0.0.0.0:$PORT



