#!/bin/bash
python -m celery -A traApp worker --loglevel INFO