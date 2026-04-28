import csv
import json
from io import StringIO
from app.models.document import Document


def export_txt(doc: Document) -> str:
    lines = [
        f"ДОКУМЕНТ #{doc.id}",
        "=" * 60,
    ]
    pt = doc.processed_text
    if pt:
        lines += ["\n[ИСХОДНЫЙ ТЕКСТ OCR]", pt.raw_text or "(нет данных)"]
        lines += ["\n[ОЧИЩЕННЫЙ ТЕКСТ]", pt.cleaned_text or "(нет данных)"]
        if pt.ocr_confidence is not None:
            lines.append(f"\nКачество OCR: {pt.ocr_confidence:.1f}%")

    if doc.themes:
        lines.append("\n[ТЕМЫ И СЕГМЕНТЫ]")
        for theme in doc.themes:
            lines.append(f"\n--- Тема {theme.order + 1}: {theme.theme_label} ---")
            if theme.keywords:
                lines.append(f"Ключевые слова: {theme.keywords}")
            if theme.confidence is not None:
                lines.append(f"Уверенность: {theme.confidence:.2f}")
            for seg in theme.segments:
                lines.append(f"  • {seg.segment_text}")

    return "\n".join(lines)


def export_json(doc: Document) -> dict:
    pt = doc.processed_text
    return {
        "document_id": doc.id,
        "status": doc.status,
        "ocr_confidence": pt.ocr_confidence if pt else None,
        "raw_text": pt.raw_text if pt else None,
        "cleaned_text": pt.cleaned_text if pt else None,
        "themes": [
            {
                "id": t.id,
                "label": t.theme_label,
                "keywords": t.keywords,
                "order": t.order,
                "confidence": t.confidence,
                "segments": [
                    {"text": s.segment_text, "order": s.order,
                     "start_char": s.start_char, "end_char": s.end_char}
                    for s in t.segments
                ],
            }
            for t in doc.themes
        ],
    }


def export_csv(doc: Document) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["theme_order", "theme_label", "keywords", "confidence",
                     "segment_order", "segment_text"])
    for theme in doc.themes:
        for seg in theme.segments:
            writer.writerow([
                theme.order, theme.theme_label, theme.keywords,
                theme.confidence, seg.order, seg.segment_text,
            ])
    return output.getvalue()
