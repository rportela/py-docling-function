# Define sets of file extensions that are considered binary or text.
from datetime import datetime, timezone
from email import message_from_bytes, policy
from email.message import EmailMessage
import hashlib
from io import BytesIO
import os
from typing import List, Optional
from blake3 import blake3
from pydantic import BaseModel
from docling_core.types.io import DocumentStream
from docling_core.types.doc.document import DoclingDocument
from docling.document_converter import DocumentConverter

from app.AzureContainer import AzureBlobContainer, get_content_by_hash_container


BINARY_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
}
TEXT_EXTENSIONS = {
    ".md",
    ".markdown",
    ".html",
    ".htm",
    ".xhtml",
    ".csv",
    ".txt",
    ".xml",
}


SUPPORTED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "text/markdown": ".md",
    "text/asciidoc": ".txt",
    "text/plain": ".txt",
    "text/html": ".html",
    "application/xhtml+xml": ".xhtml",
    "text/xml": ".xml",
    "application/xml": ".xml",
    "text/csv": ".csv",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
    "image/bmp": ".bmp",
    "message/rfc822": ".eml",  # email!
}


def is_supported_attachment(filename: str | None) -> bool:
    """
    Check if an attachment is of a supported file type.
    """
    if filename is None:
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in BINARY_EXTENSIONS or ext in TEXT_EXTENSIONS


def is_supported_mime_type(content_type: str) -> bool:
    """
    Check if a MIME type is supported.
    """
    return content_type.lower() in SUPPORTED_MIME_TYPES.keys()


class DoclingConversionResult(BaseModel):
    started_at: str
    seconds_taken: float
    content_type: str
    content_hash: str
    document: DoclingDocument
    filename: str | None = None
    attachments: Optional[List["DoclingConversionResult"]] = None


class DoclingConverter:
    """
    A class to handle the conversion of documents to DoclingDocument format.
    It can convert email messages, binary files, and other supported formats.
    """

    _converter: DocumentConverter
    _blobs: AzureBlobContainer

    def __init__(self):
        self._converter = DocumentConverter()
        self._blobs = get_content_by_hash_container()

    def _convert(
        self, content_type: str, content_bytes: bytes, filename: str | None = None
    ) -> DoclingConversionResult:
        """
        Convert the content bytes to document conversion result.
        """
        started_at = datetime.now(tz=timezone.utc)
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        stream = DocumentStream(
            name=filename or content_type, stream=BytesIO(content_bytes)
        )
        result = self._converter.convert(stream)
        return DoclingConversionResult(
            started_at=started_at.isoformat(),
            seconds_taken=(datetime.now(tz=timezone.utc) - started_at).total_seconds(),
            content_type=content_type,
            content_hash=content_hash,
            document=result.document,
            filename=filename,
        )

    def _convert_email_attachment(
        self, part: EmailMessage
    ) -> Optional[DoclingConversionResult]:
        """
        Convert a single email attachment part to a DoclingDocument if it is supported.
        """
        filename = part.get_filename()
        if not filename or not is_supported_attachment(filename):
            return None
        content_type = part.get_content_type()
        if not is_supported_mime_type(content_type):
            return None
        content: bytes = part.get_payload(decode=True)  # type: ignore
        if content is None:
            return None
        return self._convert(content_type, content, filename)

    def _convert_email_body(self, msg: EmailMessage) -> DoclingConversionResult:
        """
        Convert an EmailMessage BODY to a Conversion result.
        """
        # Attempt to get a preferred body (HTML if available, then plain text)
        body_part = msg.get_body(preferencelist=("html", "plain"))
        content = body_part.get_content() if body_part else msg.get_content()
        content_bytes: bytes = content.encode("utf-8")
        content_type = msg.get_content_type()
        filename = msg.get_filename()
        if filename is None:
            filename = msg.get("Subject", "EmailMessage")
        return self._convert(content_type, content_bytes, filename)

    def _convert_email(self, email_message: EmailMessage) -> DoclingConversionResult:
        """
        Convert an EmailMessage to a main DoclingDocument and a list of child documents for each supported attachment.
        """
        result = self._convert_email_body(email_message)
        result.attachments = []
        for part in email_message.iter_attachments():
            att = self._convert_email_attachment(part)
            if att is not None:
                result.attachments.append(att)
        return result

    def get_cached(self, content_hash: str) -> DoclingConversionResult | None:
        """
        Check if the content is already cached in the blob storage.
        """
        blob_name = f"{content_hash}/docling.json"
        blob_bytes = self._blobs.get_bytes(blob_name)
        if blob_bytes is not None:
            # Deserialize the blob bytes to DoclingConversionResult
            result = DoclingConversionResult.model_validate_json(
                blob_bytes.decode("utf-8")
            )
            if result.content_hash != content_hash:
                raise ValueError(
                    f"Content hash mismatch {result.content_hash} != {content_hash}"
                )
        return None

    def convert(
        self, content_type: str, content: bytes, filename: Optional[str]
    ) -> DoclingConversionResult:
        """
        Convert binary content to a DoclingDocument.
        """

        content_hash = blake3(content).hexdigest()

        # checks the cache
        cached = self.get_cached(content_hash)
        if cached is not None:
            return cached

        # checks the content type
        content_type = content_type.lower()
        if content_type not in SUPPORTED_MIME_TYPES:
            raise ValueError(f"Unsupported MIME type: {content_type}")

        result: DoclingConversionResult
        # checks if message
        if content_type == "message/rfc822":
            # Handle email conversion separately
            msg = message_from_bytes(
                content, policy=policy.default, _class=EmailMessage
            )
            result = self._convert_email(msg)
        else:
            result = self._convert(content_type, content, filename)

        # Save the result to blob storage
        blob_name = f"{content_hash}/docling.json"
        self._blobs.set_bytes(blob_name, result.model_dump_json().encode("utf-8"))
        return result
