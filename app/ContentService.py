from datetime import datetime, timezone
from blake3 import blake3
from app.ContentModel import SUPPORTED_MIME_TYPES, ContentModel
from app.AzureContainer import AzureBlobContainer, get_content_by_hash_container
from app.DoclingService import DoclingService
from docling_core.types.doc.document import DoclingDocument


class ContentService:

    _blobs: AzureBlobContainer
    _docling: DoclingService

    def __init__(self):
        self._blobs = get_content_by_hash_container()
        self._docling = DoclingService()

    def get_status(self, hash: str) -> ContentModel | None:
        """
        Get the status of the content by hash from the Azure Blob Storage.
        """
        blob_name = f"{hash}/index.json"
        blob_bytes = self._blobs.get_bytes(blob_name)
        if blob_bytes is None:
            return None
        return ContentModel.model_validate_json(blob_bytes.decode("utf-8"))

    def save_status(self, model: ContentModel) -> None:
        """
        Save the content status to the Azure Blob Storage.
        """
        blob_name = f"{model.hash}/index.json"
        self._blobs.set_bytes(blob_name, model.model_dump_json().encode("utf-8"))

    def _process_original(
        self, model: ContentModel, original_bytes: bytes, overwrite: bool = False
    ):
        """
        Check if the original content exists in the Azure Blob Storage.
        """
        original_ext = SUPPORTED_MIME_TYPES.get(model.content_type, ".bin")
        blob_name = f"{model.hash}/original{original_ext}"
        original_date = self._blobs.get_blob_date(blob_name)
        if original_date is None or overwrite:
            self._blobs.set_bytes(blob_name, original_bytes)
            model.created_at = datetime.now(tz=timezone.utc).isoformat()
            self.save_status(model)
        else:
            model.created_at = original_date.isoformat()

    def _check_markdown(
        self, model: ContentModel, docling: DoclingDocument, overwrite: bool = False
    ) -> str:
        blob_name = f"{model.hash}/original.md"
        markdown_date = self._blobs.get_blob_date(blob_name)
        if markdown_date is None or overwrite:
            markdown = docling.export_to_markdown()
            self._blobs.set_bytes(blob_name, markdown.encode("utf-8"))
            model.markdown_date = datetime.now(tz=timezone.utc).isoformat()
            self.save_status(model)
        else:
            markdown_bytes = self._blobs.get_bytes(blob_name)
            assert markdown_bytes is not None, "Markdown bytes should not be None"
            markdown = markdown_bytes.decode("utf-8")
        return markdown

    def process(
        self,
        original_bytes: bytes,
        content_type: str,
        filename: str,
        overwrite: bool = False,
    ) -> ContentModel:
        """
        Get the content by hash from the Azure Blob Storage.
        If it does not exist, store it and return the content model.
        """
        hash = blake3(original_bytes).hexdigest()
        model = self.get_status(hash)
        if model is None or overwrite:
            model = ContentModel(
                hash=hash,
                content_type=content_type,
                filename=filename,
                size=len(original_bytes),
                created_at=datetime.now(tz=timezone.utc).isoformat(),
            )
            self._process_original(model, original_bytes, overwrite)
        docling = self._docling.get_docling(model, original_bytes, overwrite)
        if model.markdown_date is None:
            self._check_markdown(model, docling, overwrite)
        return model
