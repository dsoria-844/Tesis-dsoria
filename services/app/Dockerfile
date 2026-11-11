FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# postgresql-client: lo usan las pruebas (psql) para crear la base con los mismos scripts de db/init
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY hp ./hp
COPY tests ./tests
RUN useradd --uid 10001 --create-home app
USER app
