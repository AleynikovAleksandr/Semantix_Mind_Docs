"""
NLP-анализ: тематическое моделирование через эмбеддинги.

Модель загружается ОДИН РАЗ при старте worker'а (глобальный синглтон),
чтобы не тратить 5-10 сек на каждый документ.

Поддерживаемые модели (настраивается через EMBEDDING_MODEL в .env):
  - sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2  (по умолчанию, ~470MB)
  - sentence-transformers/LaBSE                                   (качественнее, ~1.8GB)
  - BAAI/bge-m3                                                   (state-of-art multilingual)

Примечание: google/embedding-gemma-300m требует HF_TOKEN и особого доступа.
Если у вас есть токен — раскомментируйте блок в _load_model().
"""

import json
import os
import re
from loguru import logger

# ── Глобальный синглтон модели ────────────────────────────────────────────────
_model = None


def _load_model():
    global _model
    if _model is not None:
        return _model

    model_name = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    logger.info(f"Загрузка модели эмбеддингов: {model_name}")

    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(model_name)
        logger.info(f"Модель загружена: {model_name}")

        # ── Как использовать google/embedding-gemma-300m ──────────────────
        # Эта модель требует HF_TOKEN и особого доступа на HuggingFace.
        # Раскомментируйте, если у вас есть доступ:
        #
        # from transformers import AutoTokenizer, AutoModel
        # import torch
        # hf_token = os.getenv("HF_TOKEN")
        # tokenizer = AutoTokenizer.from_pretrained(
        #     "google/gemma-3n-e2b-it",   # замените на актуальное имя
        #     token=hf_token
        # )
        # raw_model = AutoModel.from_pretrained(
        #     "google/gemma-3n-e2b-it",
        #     token=hf_token
        # )
        # _model = {"tokenizer": tokenizer, "model": raw_model, "type": "hf"}
        # ─────────────────────────────────────────────────────────────────

    except Exception as e:
        logger.error(f"Не удалось загрузить модель '{model_name}': {e}")
        logger.warning("Переключаемся на TF-IDF fallback")
        _model = "fallback"

    return _model


# Загружаем модель при импорте модуля (т.е. при старте worker'а)
_load_model()


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """Разбивает текст на предложения."""
    sentences = re.split(r"(?<=[.!?;])\s+|\n{2,}", text)
    return [s.strip() for s in sentences if len(s.strip()) > 15]


def _tfidf_keywords(sentences: list[str], top_n: int = 8) -> list[str]:
    """TF-IDF ключевые слова из набора предложений."""
    if len(sentences) < 2:
        return []
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        vec = TfidfVectorizer(max_features=100, min_df=1)
        tfidf = vec.fit_transform(sentences)
        scores = tfidf.mean(axis=0).A1
        vocab = vec.get_feature_names_out()
        top_idx = scores.argsort()[-top_n:][::-1]
        return [vocab[i] for i in top_idx]
    except Exception:
        return []


# ── Основная функция ──────────────────────────────────────────────────────────

def analyze_topics(cleaned_text: str, n_topics: int = 5) -> list[dict]:
    """
    Тематический анализ текста.

    Возвращает список тем:
    [
      {
        "label": str,
        "keywords": str (JSON список),
        "segments": [str],
        "confidence": float
      }
    ]
    """
    if not cleaned_text or len(cleaned_text.strip()) < 50:
        return [{
            "label": "Основная тема",
            "keywords": "[]",
            "segments": [cleaned_text.strip()],
            "confidence": 1.0,
        }]

    sentences = _split_sentences(cleaned_text)
    if len(sentences) < 3:
        return [{
            "label": "Основная тема",
            "keywords": json.dumps(_tfidf_keywords(sentences or [cleaned_text]), ensure_ascii=False),
            "segments": sentences or [cleaned_text],
            "confidence": 1.0,
        }]

    n_clusters = min(n_topics, max(1, len(sentences) // 3))
    model = _load_model()

    if model == "fallback" or model is None:
        return _fallback_topics(sentences, n_clusters)

    return _embedding_topics(sentences, n_clusters, model)


def _embedding_topics(sentences: list[str], n_clusters: int, model) -> list[dict]:
    """Кластеризация через sentence-transformer эмбеддинги + KMeans."""
    try:
        import numpy as np
        from sklearn.cluster import KMeans

        logger.info(f"Векторизация {len(sentences)} предложений...")
        embeddings = model.encode(sentences, show_progress_bar=False, batch_size=32)

        logger.info(f"KMeans кластеризация: {n_clusters} тем")
        km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = km.fit_predict(embeddings)

        # Считаем среднюю дистанцию до центроида (уверенность)
        max_inertia = float(km.inertia_) or 1.0

        topics = []
        for cluster_id in range(n_clusters):
            idxs = [i for i, l in enumerate(labels) if l == cluster_id]
            if not idxs:
                continue
            cluster_sentences = [sentences[i] for i in idxs]
            keywords = _tfidf_keywords(cluster_sentences)
            label = keywords[0].capitalize() if keywords else f"Тема {cluster_id + 1}"

            # Уверенность: насколько плотный кластер
            cluster_embeddings = embeddings[idxs]
            centroid = km.cluster_centers_[cluster_id]
            dists = np.linalg.norm(cluster_embeddings - centroid, axis=1)
            avg_dist = float(dists.mean())
            confidence = max(0.0, min(1.0, 1.0 - avg_dist / 2.0))

            topics.append({
                "label": label,
                "keywords": json.dumps(keywords, ensure_ascii=False),
                "segments": cluster_sentences,
                "confidence": round(confidence, 3),
            })

        logger.info(f"Выделено {len(topics)} тем через эмбеддинги")
        return topics

    except Exception as e:
        logger.error(f"Embedding topics error: {e}, fallback")
        return _fallback_topics(sentences, n_clusters)


def _fallback_topics(sentences: list[str], n_clusters: int) -> list[dict]:
    """Простое разбиение на равные блоки + TF-IDF."""
    chunk = max(1, len(sentences) // n_clusters)
    topics = []
    for i in range(n_clusters):
        block = sentences[i * chunk: (i + 1) * chunk]
        if not block:
            continue
        keywords = _tfidf_keywords(block)
        label = keywords[0].capitalize() if keywords else f"Тема {i + 1}"
        topics.append({
            "label": label,
            "keywords": json.dumps(keywords, ensure_ascii=False),
            "segments": block,
            "confidence": 0.6,
        })
    logger.info(f"Fallback: {len(topics)} тем")
    return topics
