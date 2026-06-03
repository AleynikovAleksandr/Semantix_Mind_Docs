#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT_DIR
MODEL_DIR="${ROOT_DIR}/worker/model"
EMBEDDING_DIR="${MODEL_DIR}/embeddinggemma-300m"
TESSERACT_DIR="${MODEL_DIR}/tesseract"
TESSDATA_DIR="${TESSERACT_DIR}/tessdata"
HF_MODEL_ID="${HF_MODEL_ID:-google/embeddinggemma-300m}"
DOWNLOAD_EMBEDDING_MODEL="${DOWNLOAD_EMBEDDING_MODEL:-0}"

mkdir -p "${EMBEDDING_DIR}" "${TESSERACT_DIR}" "${TESSDATA_DIR}"

echo "[1/3] Checking embedding model directory: ${EMBEDDING_DIR}"
if [ -f "${EMBEDDING_DIR}/config.json" ] || [ -f "${EMBEDDING_DIR}/model.safetensors" ]; then
    echo "Embedding model files already exist; skipping download."
elif [ "${DOWNLOAD_EMBEDDING_MODEL}" = "1" ]; then
    echo "Downloading embedding model: ${HF_MODEL_ID}"
    python - <<'PY'
import os
import subprocess
import sys

try:
    from huggingface_hub import snapshot_download
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub>=0.23"])
    from huggingface_hub import snapshot_download

root = os.environ["ROOT_DIR"]
local_dir = os.path.join(root, "worker", "model", "embeddinggemma-300m")
model_id = os.getenv("HF_MODEL_ID", "google/embeddinggemma-300m")
token = os.getenv("HF_TOKEN") or None

snapshot_download(
    repo_id=model_id,
    local_dir=local_dir,
    token=token,
    ignore_patterns=["*.msgpack", "*.h5", "*.ot"],
)
print(f"Embedding model downloaded to: {local_dir}")
PY
else
    echo "Embedding model download disabled (set DOWNLOAD_EMBEDDING_MODEL=1 to download)."
fi

echo "[2/3] Preparing local Tesseract binary"
if command -v tesseract >/dev/null 2>&1; then
    cp "$(command -v tesseract)" "${TESSERACT_DIR}/tesseract"
    chmod +x "${TESSERACT_DIR}/tesseract"
    echo "Copied tesseract binary to: ${TESSERACT_DIR}/tesseract"
else
    echo "WARNING: tesseract binary was not found in PATH; leaving existing file if present." >&2
fi

echo "[3/3] Preparing tessdata language files"
TESSDATA_SOURCE=""
for candidate in \
    "${TESSDATA_PREFIX:-}" \
    "/usr/share/tesseract-ocr/5/tessdata" \
    "/usr/share/tesseract-ocr/4.00/tessdata" \
    "/usr/share/tessdata"; do
    if [ -n "${candidate}" ] && [ -d "${candidate}" ]; then
        TESSDATA_SOURCE="${candidate}"
        break
    fi
done

if [ -n "${TESSDATA_SOURCE}" ]; then
    for lang in eng rus; do
        if [ -f "${TESSDATA_SOURCE}/${lang}.traineddata" ]; then
            cp "${TESSDATA_SOURCE}/${lang}.traineddata" "${TESSDATA_DIR}/${lang}.traineddata"
            echo "Copied ${lang}.traineddata from ${TESSDATA_SOURCE}"
        else
            echo "WARNING: ${lang}.traineddata not found in ${TESSDATA_SOURCE}" >&2
        fi
    done
else
    echo "WARNING: system tessdata directory was not found; install tesseract language packages first." >&2
fi

cat <<MSG

Done.
Prepared paths:
  ${EMBEDDING_DIR}
  ${TESSERACT_DIR}/tesseract
  ${TESSDATA_DIR}

Recommended .env values:
  EMBEDDING_MODEL=/app/worker/model/embeddinggemma-300m
  TESSERACT_CMD=/app/worker/model/tesseract/tesseract
  TESSDATA_PREFIX=/app/worker/model/tesseract/tessdata
MSG
