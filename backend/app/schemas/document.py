from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.models.document import DocumentStatus


class DocumentUploadResponse(BaseModel):
    document_id: int
    file_name: str
    status: DocumentStatus
    celery_task_id: Optional[str]
    message: str


class DocumentStatusResponse(BaseModel):
    document_id: int
    status: DocumentStatus
    page_count: Optional[int]
    processing_time: Optional[float]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    id: int
    status: DocumentStatus
    page_count: Optional[int]
    processing_time: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class TopicSegmentOut(BaseModel):
    id: int
    segment_text: str
    order: int
    start_char: Optional[int]
    end_char: Optional[int]

    model_config = {"from_attributes": True}


class ThemeOut(BaseModel):
    id: int
    theme_label: str
    keywords: Optional[str]
    order: int
    confidence: Optional[float]
    segments: List[TopicSegmentOut] = []

    model_config = {"from_attributes": True}


class DocumentResultResponse(BaseModel):
    document_id: int
    status: DocumentStatus
    raw_text: Optional[str]
    cleaned_text: Optional[str]
    ocr_confidence: Optional[float]
    themes: List[ThemeOut] = []
