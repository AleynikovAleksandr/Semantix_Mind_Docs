FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    libopencv-dev \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    libpq-dev \
    libmagic1 \
    gcc \
    g++ \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY worker ./worker
COPY scripts ./scripts

RUN bash scripts/setup_worker_assets.sh

RUN mkdir -p /app/uploads /app/core/logging
