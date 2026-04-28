from pydantic import BaseModel


class TextSearchResult(BaseModel):
    document_id: int
    rank: float


class SemanticSearchResult(BaseModel):
    document_id: int
    theme_index: int
    distance: float
