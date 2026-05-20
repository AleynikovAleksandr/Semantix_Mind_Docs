"""
NLP-анализ: тематическое моделирование через embeddinggemma + KeyBERT
Локальная модель: ./worker/model/embeddinggemma-300m
"""

import json
import os
import re
from loguru import logger

_model = None
_kw_model = None


# ==========================
# Загрузка модели (singleton)
# ==========================
def _load_model():
    global _model, _kw_model

    if _model is not None:
        return _model

    try:
        from transformers import AutoTokenizer, AutoModel
        from keybert import KeyBERT
        import torch

        model_path = "./worker/model/embeddinggemma-300m"

        logger.info(f"Загрузка embeddinggemma из {model_path}")

        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModel.from_pretrained(model_path)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        model.eval()

        kw_model = KeyBERT(model)

        _model = {
            "tokenizer": tokenizer,
            "model": model,
            "device": device,
        }
        _kw_model = kw_model

        logger.info("Модель embeddinggemma загружена")

    except Exception as e:
        logger.error(f"Ошибка загрузки embeddinggemma: {e}")
        _model = "fallback"

    return _model


# Загружаем при старте
_load_model()


# ==========================
# Утилиты
# ==========================
def _split_sentences(text: str):
    sentences = re.split(r"(?<=[.!?;])\s+|\n{2,}", text)
    return [s.strip() for s in sentences if len(s.strip()) > 15]


def _tfidf_keywords(sentences, top_n=8):
    if len(sentences) < 2:
        return []
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        vec = TfidfVectorizer(max_features=100)
        tfidf = vec.fit_transform(sentences)

        scores = tfidf.mean(axis=0).A1
        vocab = vec.get_feature_names_out()

        top_idx = scores.argsort()[-top_n:][::-1]
        return [vocab[i] for i in top_idx]
    except Exception:
        return []


# ==========================
# Embeddings
# ==========================
def _encode(sentences, model_dict):
    import torch

    tokenizer = model_dict["tokenizer"]
    model = model_dict["model"]
    device = model_dict["device"]

    inputs = tokenizer(
        sentences,
        padding=True,
        truncation=True,
        return_tensors="pt",
    ).to(device)

    with torch.no_grad():
        outputs = model(**inputs)
        embeddings = outputs.last_hidden_state.mean(dim=1)

    return embeddings.cpu().numpy()


# ==========================
# Основная функция
# ==========================
def analyze_topics(text: str, n_topics=5):
    if not text or len(text.strip()) < 50:
        return [{
            "label": "Основная тема",
            "keywords": "[]",
            "segments": [text.strip() if text else ""],
            "confidence": 1.0,
        }]

    sentences = _split_sentences(text)

    if len(sentences) < 3:
        return [{
            "label": "Основная тема",
            "keywords": json.dumps(_tfidf_keywords(sentences), ensure_ascii=False),
            "segments": sentences,
            "confidence": 1.0,
        }]

    model = _load_model()

    if model == "fallback":
        return _fallback(sentences, n_topics)

    return _embedding_topics(sentences, n_topics, model)


# ==========================
# Основная логика
# ==========================
def _embedding_topics(sentences, n_topics, model):
    import numpy as np
    from sklearn.cluster import KMeans

    embeddings = _encode(sentences, model)

    n_clusters = min(n_topics, max(1, len(sentences) // 3))

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(embeddings)

    topics = []

    for cid in range(n_clusters):
        idxs = [i for i, l in enumerate(labels) if l == cid]
        if not idxs:
            continue

        cluster_sentences = [sentences[i] for i in idxs]
        cluster_embeddings = embeddings[idxs]
        centroid = km.cluster_centers_[cid]

        try:
            keywords = [
                kw for kw, _ in _kw_model.extract_keywords(
                    " ".join(cluster_sentences),
                    top_n=5,
                )
            ]
        except Exception:
            keywords = _tfidf_keywords(cluster_sentences)

        label = keywords[0].capitalize() if keywords else f"Тема {cid + 1}"

        dists = np.linalg.norm(cluster_embeddings - centroid, axis=1)
        avg_dist = float(dists.mean())
        confidence = 1.0 / (1.0 + avg_dist)

        topics.append({
            "label": label,
            "keywords": json.dumps(keywords, ensure_ascii=False),
            "segments": cluster_sentences,
            "confidence": round(confidence, 3),
        })

    return topics


# ==========================
# Fallback
# ==========================
def _fallback(sentences, n_topics):
    chunk = max(1, len(sentences) // n_topics)

    topics = []

    for i in range(n_topics):
        block = sentences[i * chunk:(i + 1) * chunk]
        if not block:
            continue

        keywords = _tfidf_keywords(block)
        label = keywords[0] if keywords else f"Тема {i + 1}"

        topics.append({
            "label": label,
            "keywords": json.dumps(keywords, ensure_ascii=False),
            "segments": block,
            "confidence": 0.5,
        })

    return topics
