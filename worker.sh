#!/bin/bash
python -m celery -A traApp worker --loglevel INFO --concurrency=10