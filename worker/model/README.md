# Local model assets

Place local runtime assets here:

- `embeddinggemma-300m/` — local HuggingFace-compatible embedding model files.
- `tesseract/tesseract` — local Tesseract binary (executable).
- `tesseract/tessdata/` — Tesseract language data (`*.traineddata`).

These paths are used by:
- `worker/nlp_analyzer.py`
- `worker/ocr_processor.py`
