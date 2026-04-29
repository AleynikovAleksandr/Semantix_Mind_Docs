# Document Processing System - `Semantix_Mind_Docs`

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)
![pgvector](https://img.shields.io/badge/pgvector-0.7-orange)
![Celery](https://img.shields.io/badge/Celery-5.4-brightgreen)
![Redis](https://img.shields.io/badge/Redis-7-red)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![Tesseract](https://img.shields.io/badge/Tesseract-OCR-yellow)
![HuggingFace](https://img.shields.io/badge/HuggingFace-Transformers-orange)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

An automated document processing system that extracts text from low-quality PDFs and images using OCR, cleans and normalizes the output, performs NLP-based topic modeling, and exposes both full-text and semantic search over the results via a REST API.

---

## Current Features

- **Document Upload** — accepts PDF, JPEG, PNG, TIFF files up to 50 MB
- **OCR Pipeline** — image preprocessing (deskew, denoise, binarization) with Tesseract + OpenCV
- **Text Cleaning** — normalization of OCR artifacts, whitespace, control characters
- **Topic Modeling** — sentence-transformer embeddings + KMeans clustering to extract named themes and segments
- **Full-Text Search** — PostgreSQL `tsvector` / `tsquery` with GIN index for fast keyword-based search across documents and topics
- **Semantic Search** — cosine similarity over stored embeddings using `pgvector` HNSW index for meaning-aware retrieval
- **Export** — results available as TXT, JSON, or CSV
- **Authentication** — JWT access/refresh tokens + API Key support (per-key permissions: read / write / delete)
- **Async Processing** — Celery workers with Redis broker; task status trackable via API
- **Request Logging** — all HTTP requests logged to PostgreSQL with response time and IP
- **Swagger UI** — interactive API documentation at `/docs`
- **Flower Dashboard** — Celery task monitoring at port `5555`

## Model Information

### EmbeddingGemma-300M

EmbeddingGemma-300M is a lightweight, high-performance text embedding model developed by Google DeepMind.
With only 300 million parameters, it offers an excellent balance between speed, memory efficiency, and embedding quality. The model is designed for semantic search, clustering, topic modeling, and retrieval tasks across more than 100 languages, including strong support for Russian.

**Key Features:**

- 300M parameters – fast inference and low memory footprint
- Context length: up to 2048 tokens
- Multilingual support: 100+ languages
- Supports Matryoshka Representation Learning (flexible embedding dimensions: 768, 512, 256, etc.)
- Optimized for on-device and server-side use
- Excellent performance on multilingual semantic similarity and clustering benchmarks

**Ideal For:**

- Building semantic search systems
- Topic modeling with BERTopic
- Document clustering and segmentation
- Retrieval-Augmented Generation (RAG) pipelines
- Post-OCR text analysis

This model is particularly well-suited for projects that require fast and efficient multilingual embeddings without sacrificing too much quality.

### 4. Open API docs

```
Swagger UI  →  http://localhost:8000/docs
ReDoc       →  http://localhost:8000/redoc
Flower      →  http://localhost:5555
```

## API Endpoints

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Register a new user |
| `POST` | `/api/auth/login` | Login → returns access + refresh JWT |
| `POST` | `/api/auth/refresh` | Refresh access token |
| `POST` | `/api/auth/logout` | Logout (client deletes tokens) |
| `GET`  | `/api/auth/me` | Current user info |
| `POST` | `/api/auth/api-keys` | Create API key (shown once) |
| `GET`  | `/api/auth/api-keys` | List API keys |
| `DELETE` | `/api/auth/api-keys/{id}` | Revoke API key |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/upload` | Upload PDF / image |
| `GET`  | `/api/documents/` | List user's documents |
| `GET`  | `/api/documents/{id}/status` | Processing status |
| `GET`  | `/api/documents/{id}/results` | Full results (text + themes) |
| `DELETE` | `/api/documents/{id}` | Delete document and all data |

### Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/export/{id}/txt` | Export as plain text |
| `GET` | `/api/export/{id}/json` | Export as JSON |
| `GET` | `/api/export/{id}/csv` | Export themes/segments as CSV |

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/search/text?q=...` | Full-text search (PostgreSQL FTS) |
| `GET` | `/api/search/semantic?q=...` | Semantic search (pgvector cosine) |


## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL async URL |
| `REDIS_URL` | — | Redis URL |
| `JWT_SECRET_KEY` | **required** | Secret for JWT signing |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | HuggingFace model name |
| `EMBEDDING_DIM` | `384` | Vector dimension (must match schema) |
| `TESSERACT_LANG` | `rus+eng` | OCR languages |
| `MAX_FILE_SIZE_MB` | `50` | Upload size limit |
| `HF_TOKEN` | optional | HuggingFace token (private models) |

---

## Application Notes

- **Model Loading:** The embedding model loads on worker startup (~10–20 seconds on CPU). Subsequent document processing uses the cached model — no reload per document.
- **Prediction Speed:** After the first load, embedding inference is fast even on CPU thanks to the 300M parameter size.
- **Compatibility:** Runs on laptops, servers, and Raspberry Pi 4/5.
- **Resource Usage:** Optimized to use minimal CPU and memory for fast inference. The `hf_cache` Docker volume prevents re-downloading the model on restart.
- **Reliability:** Stable for continuous local usage. Celery tasks have soft (10 min) and hard (11 min) timeouts to prevent hangs.
- **Deployment:** Fully Dockerized with separate containers for API, worker, PostgreSQL, Redis, and Flower monitoring.
- **Search Indexes:** Built automatically after each document is processed by the Celery pipeline — no manual steps required.

## Author

Developed by **Aleynikov Aleksandr**
Contact: [aleynikov.aleksandr@icloud.com](mailto:aleynikov.aleksandr@icloud.com)
