FROM python:3.9-slim-bullseye

WORKDIR /app
COPY . /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev wkhtmltopdf && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN playwright install-deps && playwright install

COPY init.sh /app/init.sh
RUN chmod +x /app/init.sh

EXPOSE 9999