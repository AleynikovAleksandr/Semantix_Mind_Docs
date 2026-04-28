import pytest
from worker.text_cleaner import clean_text
from worker.nlp_analyzer import analyze_topics, _split_sentences


def test_clean_removes_control_chars():
    raw = "Привет\x00мир\x1f!"
    result = clean_text(raw)
    assert "\x00" not in result
    assert "\x1f" not in result


def test_clean_normalizes_whitespace():
    raw = "Слово   с   лишними    пробелами"
    result = clean_text(raw)
    assert "   " not in result


def test_clean_removes_garbage_lines():
    raw = "Нормальное предложение.\n###\nЕщё одно нормальное предложение."
    result = clean_text(raw)
    assert "###" not in result
    assert "Нормальное" in result


def test_clean_keeps_short_important_lines():
    """Короткие строки с цифрами/буквами должны сохраняться."""
    raw = "Раздел 1\nA.\nОбычный текст здесь."
    result = clean_text(raw)
    assert "Раздел 1" in result


def test_clean_limits_empty_lines():
    raw = "Строка 1\n\n\n\n\n\nСтрока 2"
    result = clean_text(raw)
    assert result.count("\n\n\n") == 0


def test_split_sentences():
    text = "Первое предложение. Второе предложение! Третье? Четвёртое."
    sentences = _split_sentences(text)
    assert len(sentences) >= 2


def test_analyze_topics_returns_list():
    text = (
        "Машинное обучение позволяет компьютерам учиться на данных. "
        "Нейронные сети используются для распознавания изображений. "
        "Базы данных хранят структурированную информацию для приложений. "
        "SQL является языком запросов к реляционным базам данных. "
        "Python — популярный язык программирования для анализа данных."
    )
    topics = analyze_topics(text, n_topics=2)
    assert isinstance(topics, list)
    assert len(topics) >= 1
    for t in topics:
        assert "label" in t
        assert "segments" in t
        assert "keywords" in t
        assert isinstance(t["segments"], list)
        assert len(t["segments"]) > 0


def test_analyze_topics_short_text():
    text = "Очень короткий текст."
    topics = analyze_topics(text)
    assert len(topics) == 1
    assert topics[0]["label"] == "Основная тема"


def test_analyze_topics_confidence():
    text = " ".join([
        "Предложение о машинном обучении и нейросетях." * 3,
        "Предложение о базах данных и SQL." * 3,
    ])
    topics = analyze_topics(text, n_topics=2)
    for t in topics:
        assert 0.0 <= t["confidence"] <= 1.0
