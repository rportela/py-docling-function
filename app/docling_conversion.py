from datetime import datetime, timezone
import hashlib
import os
import re

from io import BytesIO
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import List, Optional

# Assuming this is the correct import for DoclingDocument
from docling_core.types.io import DocumentStream
from docling_core.types.doc.document import DoclingDocument
from docling.document_converter import DocumentConverter
from pydantic import BaseModel
from collections import Counter
from typing import Set
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.types.doc.document import DoclingDocument

# Define sets of file extensions that are considered binary or text.
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


def is_good_chunk(chunk: str) -> bool:
    """
    Check if a chunk is a good candidate for processing.
    """
    text = chunk.strip().lower()
    boilerplate_keywords = [
        "no part may be copied",
        "is provided only to investment professionals",
        "this document is not a research report or research material",
        "this message is for information purposes only",
        "this document is being provided for the exclusive use of",
    ]
    is_boilerplate = any(kw in chunk for kw in boilerplate_keywords)
    has_metadata = bool(
        re.search(r"\bpage \d+\b", text)
        or re.search(r"\bphone\b|\bfax\b", text)
        or re.search(r"\+\d{1,3}[\s\-]?\d{3}", text)
        or re.search(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", text)
        or re.search(r"https?://[^\s]+", text)
    )
    return not is_boilerplate and not has_metadata


def clean_chunk(text: str, repeated_chunks: Set[str]) -> str:
    """
    Clean a chunk by removing repeated chunks and boilerplate text.
    """
    for rc in repeated_chunks:
        text = text.replace(rc, "")
    return text


def filter_chunks(chunks) -> List[str]:
    """
    Filter out duplicate chunks and boilerplate text.
    """
    chunk_counts = Counter(chunks)
    repeated_chunks = {c for c, count in chunk_counts.items() if count > 1}
    return [
        clean_chunk(chunk, repeated_chunks)
        for chunk in chunks
        if chunk_counts[chunk] == 1  # remove duplicates
        and is_good_chunk(chunk)  # remove boilerplate and metadata
    ]


class DoclingConversionResult(BaseModel):
    started_at: str
    seconds_taken: float
    content_type: str
    content_hash: str
    content_bytes: bytes
    document: DoclingDocument
    chunks: List[str]
    filename: str | None = None
    attachments: Optional[List["DoclingConversionResult"]] = None


class DoclingConverter:
    """
    A class to handle the conversion of documents to DoclingDocument format.
    It can convert email messages, binary files, and other supported formats.
    """

    converter: DocumentConverter
    chunker: HybridChunker

    def __init__(self):
        self.converter = DocumentConverter()
        self.chunker = HybridChunker()

    def _convert_and_chunk(
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
        result = self.converter.convert(stream)
        raw_chunks = list(self.chunker.chunk(result.document))
        chunks = filter_chunks([chunk.text for chunk in raw_chunks])
        return DoclingConversionResult(
            started_at=started_at.isoformat(),
            seconds_taken=(datetime.now(tz=timezone.utc) - started_at).total_seconds(),
            content_type=content_type,
            content_hash=content_hash,
            content_bytes=content_bytes,
            document=result.document,
            chunks=chunks,
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
        return self._convert_and_chunk(content_type, content, filename)

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
        return self._convert_and_chunk(content_type, content_bytes, filename)

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

    def convert(
        self, content_type: str, content: bytes, filename: Optional[str]
    ) -> DoclingConversionResult:
        """
        Convert binary content to a DoclingDocument.
        """
        content_type = content_type.lower()
        if content_type not in SUPPORTED_MIME_TYPES:
            raise ValueError(f"Unsupported MIME type: {content_type}")
        if content_type == "message/rfc822":
            # Handle email conversion separately
            msg = message_from_bytes(
                content, policy=policy.default, _class=EmailMessage
            )
            return self._convert_email(msg)
        else:
            return self._convert_and_chunk(content_type, content, filename)
