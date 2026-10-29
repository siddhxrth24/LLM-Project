from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ChunkResponse(BaseModel):
    """Schema for a document text chunk."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Chunk ID")
    document_id: int = Field(..., description="Parent document ID")
    chunk_index: int = Field(..., description="Index order within document")
    page_number: Optional[int] = Field(None, description="Source page number (PDF)")
    slide_number: Optional[int] = Field(None, description="Source slide number (PPTX)")
    content: str = Field(..., description="Text content of the chunk")
    source_filename: str = Field(..., description="Original source filename")


class DocumentResponse(BaseModel):
    """Schema representing an uploaded document."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Document ID")
    unit_id: int = Field(..., description="Unit ID this document belongs to")
    course_id: int = Field(..., description="Course ID")
    filename: str = Field(..., description="Sanitized unique filename on disk")
    original_filename: str = Field(..., description="Original uploaded filename")
    file_type: str = Field(..., description="File extension/type (pdf or pptx)")
    file_size: int = Field(..., description="File size in bytes")
    status: str = Field(
        ...,
        description="Processing status: pending, processing, completed, failed",
    )
    error_message: Optional[str] = Field(
        None, description="Error details if processing failed"
    )
    page_count: int = Field(default=0, description="Total pages or slides extracted")
    chunk_count: int = Field(default=0, description="Total generated text chunks")
    created_at: datetime
    updated_at: datetime
    chunks: Optional[list[ChunkResponse]] = Field(
        default=None, description="Extracted chunks if requested"
    )


class DocumentUploadResponse(BaseModel):
    """Response returned upon uploading one or more documents."""

    message: str = Field(..., description="Status summary message")
    documents: list[DocumentResponse] = Field(
        default_factory=list, description="List of uploaded documents"
    )


class DocumentStatusResponse(BaseModel):
    """Response returned when polling document processing status."""

    id: int
    status: str
    error_message: Optional[str] = None
    page_count: int = 0
    chunk_count: int = 0
