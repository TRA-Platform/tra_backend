#!/bin/bash
echo ====INSTALLING DEPENDENCIES [START]====
playwright install
echo ====INSTALLING DEPENDENCIES [END]====
python -m celery -A traApp worker --loglevel INFO