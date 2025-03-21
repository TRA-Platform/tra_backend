FROM python:3.9-slim-buster
WORKDIR /app
COPY . /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev default-libmysqlclient-dev tesseract-ocr libtesseract-dev tesseract-ocr-rus && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
EXPOSE 9999

COPY init.sh /app/init.sh

RUN chmod +x /app/init.sh
