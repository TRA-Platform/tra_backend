```bash
export LOCAL=true export SECRET_TOKEN=aHR0cDovL2xvY2FsaG9zdDo5ODc2L2luZ2VzdA\=\=; python -m celery -A traApp worker --concurrency=8 -Ofair -B
```

```bash
python manage.py graph_models -a -o schema.png
```