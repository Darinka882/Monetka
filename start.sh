#!/bin/bash
gunicorn bot:app --worker-class aiohttp.GunicornWebWorker --bind 0.0.0.0:$PORT


