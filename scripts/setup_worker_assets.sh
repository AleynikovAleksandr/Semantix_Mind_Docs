#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT_DIR
MODEL_DIR="${ROOT_DIR}/worker/model"
EMBEDDING_DIR="${MODEL_DIR}/embeddinggemma-300m"
TESSERACT_DIR="${MODEL_DIR}/tesseract"
TESSDATA_DIR="${TESSERACT_DIR}/tessdata"
HF_MODEL_ID="${HF_MODEL_ID:-google/embeddinggemma-300m}"

mkdir -p "${EMBEDDING_DIR}" "${TESSDATA_DIR}"

echo "[1/3] Downloading embedding model: ${HF_MODEL_ID}"
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

echo "[2/3] Preparing local Tesseract binary"
if command -v tesseract >/dev/null 2>&1; then
    cp "$(command -v tesseract)" "${TESSERACT_DIR}/tesseract"
    chmod +x "${TESSERACT_DIR}/tesseract"
    echo "Copied tesseract binary to: ${TESSERACT_DIR}/tesseract"
else
    cat >&2 <<'MSG'
Tesseract binary was not found in PATH.
Install it first, for example:
  Ubuntu/Debian: sudo apt-get update && sudo apt-get install -y tesseract-ocr
  macOS:         brew install tesseract
Then re-run this script.
MSG
    exit 1
fi

echo "[3/3] Downloading tessdata language files"
curl -fL "https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata" -o "${TESSDATA_DIR}/eng.traineddata"
curl -fL "https://github.com/tesseract-ocr/tessdata/raw/main/rus.traineddata" -o "${TESSDATA_DIR}/rus.traineddata"

cat <<MSG

Done.
Created/updated:
  ${EMBEDDING_DIR}
  ${TESSERACT_DIR}/tesseract
  ${TESSDATA_DIR}/eng.traineddata
  ${TESSDATA_DIR}/rus.traineddata

Recommended .env values:
  EMBEDDING_MODEL=/app/worker/model/embeddinggemma-300m
  TESSERACT_CMD=/app/worker/model/tesseract/tesseract
  TESSDATA_PREFIX=/app/worker/model/tesseract/tessdata
MSG
