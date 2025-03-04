import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel, Field

from app.services.document_service import DocumentService

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)

logger = logging.getLogger(__name__)


# Dependency for document service
def get_document_service():
    try:
        service = DocumentService()
        return service
    except Exception as e:
        logger.error(f"Error initializing document service: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Could not initialize document service: {str(e)}")


# Pydantic models for request/response validation
class DocumentMetadata(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    custom_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    document_id: str
    drive_file_id: Optional[str] = None
    filename: str
    content_length: int
    metadata: Dict[str, Any]


class SearchQuery(BaseModel):
    query: str
    limit: int = Field(5, ge=1, le=20)


class SearchResult(BaseModel):
    id: str
    score: float
    content: str
    metadata: Dict[str, Any]


class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
    count: int


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
        file: UploadFile = File(...),
        folder_id: Optional[str] = Form(None),
        metadata_json: Optional[str] = Form(None),
        document_service: DocumentService = Depends(get_document_service)
):
    """
    Upload a document for processing and indexing.

    Args:
        file: The document file to upload
        folder_id: Optional Google Drive folder ID to upload to
        metadata_json: Optional JSON string with additional metadata

    Returns:
        Metadata about the processed document
    """
    try:
        # Read file content
        file_content = await file.read()

        # Parse metadata if provided
        metadata = None
        if metadata_json:
            import json
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON")

        # Process the document
        result = await document_service.upload_document(
            file_name=file.filename,
            file_content=file_content,
            mime_type=file.content_type or "application/octet-stream",
            folder_id=folder_id,
            metadata=metadata
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResponse)
async def search_documents(
        search_query: SearchQuery,
        document_service: DocumentService = Depends(get_document_service)
):
    """
    Search for documents relevant to the provided query.

    Args:
        search_query: Search parameters

    Returns:
        List of relevant documents
    """
    try:
        results = document_service.search_documents(search_query.query, search_query.limit)

        return {
            "results": results,
            "query": search_query.query,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(
        document_id: str,
        document_service: DocumentService = Depends(get_document_service)
):
    """
    Delete a document from the vector store.

    Args:
        document_id: ID of the document to delete

    Returns:
        Success status
    """
    try:
        success = document_service.delete_document(document_id)

        if not success:
            raise HTTPException(status_code=404, detail="Document not found or could not be deleted")

        return {"success": True, "document_id": document_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))