import io
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, BinaryIO
from uuid import uuid4

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.config.settings import QDRANT_URL, QDRANT_API_KEY, OPENAI_API_KEY
from app.util.text_extractor import TextExtractor

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Service for handling document operations, including:
    - Uploading to Google Drive
    - Processing text content
    - Creating vector embeddings
    - Storing in Qdrant
    """

    def __init__(self):
        """Initialize the service with the necessary clients."""
        try:
            # Initialize Qdrant client
            self.qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

            # Initialize OpenAI embeddings
            self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

            # Initialize Google Drive service
            self.drive_service = self._initialize_drive_service()

            # Collection name for Qdrant
            self.collection_name = "chat_docs"

            # Ensure collection exists
            self._ensure_collection_exists()

            logger.info("DocumentService initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing DocumentService: {str(e)}")
            raise

    def _initialize_drive_service(self):
        """Initialize and return a Google Drive service client."""
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not credentials_path:
            logger.warning("GOOGLE_APPLICATION_CREDENTIALS not set, Google Drive features will be unavailable")
            return None

        try:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=credentials)
        except Exception as e:
            logger.error(f"Error initializing Google Drive service: {str(e)}")
            return None

    def _ensure_collection_exists(self):
        """Ensure the Qdrant collection exists, creating it if needed."""
        try:
            collections = self.qdrant_client.get_collections().collections
            collection_names = [collection.name for collection in collections]

            if self.collection_name not in collection_names:
                # Create the collection with the appropriate vector size for the embeddings model
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=1536,  # Size for text-embedding-3-small
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"Qdrant collection already exists: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error ensuring Qdrant collection exists: {str(e)}")
            raise

    async def upload_document(self, file_name: str, file_content: bytes, mime_type: str,
                              folder_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[
        str, Any]:
        """
        Process a document by:
        1. Optionally uploading to Google Drive (if folder_id is provided)
        2. Extracting text content
        3. Creating embeddings
        4. Storing in Qdrant

        Args:
            file_name: Name of the file
            file_content: Binary content of the file
            mime_type: MIME type of the file
            folder_id: Optional Google Drive folder ID to upload to
            metadata: Additional metadata to store with the document

        Returns:
            Dictionary with metadata about the processed document
        """
        try:
            drive_metadata = {}

            # Upload to Google Drive if folder ID is provided and Drive service is available
            if folder_id and self.drive_service:
                drive_metadata = self._upload_to_drive(folder_id, file_name, file_content, mime_type)
                logger.info(
                    f"Document uploaded to Google Drive: {drive_metadata.get('name')} (ID: {drive_metadata.get('id')})")

            # Extract text content from the document
            text_content = TextExtractor.extract_text_content(file_content, mime_type)

            # Skip empty documents
            if not text_content.strip():
                logger.warning(f"No text content extracted from document: {file_name}")
                return {"error": "No text content could be extracted from this document"}

            # Create vector embedding
            vector = await self.embeddings.aembed_query(text_content)

            # Generate a unique ID for the document in Qdrant
            point_id = str(uuid4())

            # Combine all metadata
            combined_metadata = {
                "name": file_name,
                "mimeType": mime_type,
                "uploadTime": datetime.utcnow().isoformat(),
                **(drive_metadata or {}),
                **(metadata or {})
            }

            # Store in Qdrant
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "content": text_content,
                        "metadata": combined_metadata,
                        "type": "document"
                    }
                )]
            )

            logger.info(f"Document processed and stored in Qdrant with ID: {point_id}")

            return {
                "document_id": point_id,
                "drive_file_id": drive_metadata.get("id") if drive_metadata else None,
                "filename": file_name,
                "content_length": len(text_content),
                "metadata": combined_metadata
            }

        except Exception as e:
            logger.error(f"Error processing document {file_name}: {str(e)}")
            raise

    def _upload_to_drive(self, folder_id: str, file_name: str, file_content: bytes, mime_type: str) -> Dict[str, Any]:
        """Upload a file to Google Drive and return its metadata."""
        if not self.drive_service:
            raise ValueError("Google Drive service is not initialized")

        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }

        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype=mime_type, resumable=True)

        file = self.drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,name,mimeType,createdTime,modifiedTime'
        ).execute()

        return file

    def search_documents(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for documents in Qdrant that are relevant to the query.

        Args:
            query: The search query
            limit: Maximum number of results to return

        Returns:
            List of document data including content and metadata
        """
        try:
            # Create query embedding
            query_vector = self.embeddings.embed_query(query)

            # Search in Qdrant
            search_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit
            )

            # Format the results
            documents = []
            for result in search_results:
                payload = result.payload
                documents.append({
                    "id": result.id,
                    "score": result.score,
                    "content": payload.get("content", ""),
                    "metadata": payload.get("metadata", {})
                })

            return documents

        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            raise

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the vector store.

        Args:
            document_id: The ID of the document to delete

        Returns:
            True if the deletion was successful
        """
        try:
            self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[document_id]
                )
            )
            logger.info(f"Document deleted from Qdrant: {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {str(e)}")
            return False