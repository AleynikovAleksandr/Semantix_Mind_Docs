import re
from loguru import logger


def clean_text(raw: str) -> str:
    """
    Нормализация OCR-текста:
    - Удаляем управляющие символы
    - Исправляем типичные OCR-артефакты
    - Нормализуем пробелы и переносы строк
    - НЕ удаляем короткие строки (могут быть важные числа/метки)
    """
    text = raw

    # 1. Управляющие символы (оставляем \n и \t)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 2. Типичные OCR-замены
    replacements = {
        "\u00a0": " ",   # неразрывный пробел
        "\u00ad": "",    # мягкий перенос
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬀ": "ff",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
    }
    for wrong, right in replacements.items():
        text = text.replace(wrong, right)

    # 3. Убираем строки только из мусорных символов (не цифры и не буквы вообще)
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Пустые строки оставляем для структуры
        if stripped == "":
            cleaned_lines.append("")
            continue
        # Строки только из спецсимволов без букв/цифр — мусор OCR
        if stripped and not re.search(r"[a-zA-Zа-яА-Я0-9]", stripped):
            continue
        cleaned_lines.append(line)

    # 4. Не более двух пустых строк подряд
    result_lines: list[str] = []
    empty_count = 0
    for line in cleaned_lines:
        if line.strip() == "":
            empty_count += 1
            if empty_count <= 2:
                result_lines.append(line)
        else:
            empty_count = 0
            result_lines.append(line)

    text = "\n".join(result_lines)

    # 5. Множественные пробелы внутри строки
    text = re.sub(r"[ \t]{2,}", " ", text)

    # 6. Пробелы в начале/конце строк
    text = "\n".join(l.rstrip() for l in text.split("\n"))

    result = text.strip()
    logger.info(f"Очистка текста: {len(raw)} → {len(result)} символов")
    return result
