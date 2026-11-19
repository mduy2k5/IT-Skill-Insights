FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir duckdb==2.0.0 psycopg2-binary==2.9.10

COPY scraper/job_crawler/load_olap.py /app/load_olap.py

ENTRYPOINT ["python", "/app/load_olap.py"]
