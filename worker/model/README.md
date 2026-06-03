# Local model assets

Place local runtime assets here:

- `embeddinggemma-300m/` — local HuggingFace-compatible embedding model files.
- `tesseract/tesseract` — local Tesseract binary (executable).
- `tesseract/tessdata/` — Tesseract language data (`*.traineddata`).

These paths are used by:
- `worker/nlp_analyzer.py`
- `worker/ocr_processor.py`

## Setup command

Run from the repository root:

```bash
bash scripts/setup_worker_assets.sh
```

Optional environment variables:

- `HF_MODEL_ID` — Hugging Face repo id, default `google/embeddinggemma-300m`.
- `HF_TOKEN` — Hugging Face token if access to the model requires authentication.

The script creates the directory structure, downloads the embedding model, copies a local `tesseract` binary, and downloads `eng`/`rus` tessdata files.
