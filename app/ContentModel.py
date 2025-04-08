from typing import List

from pydantic import BaseModel

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
    ext = filename.split(".")[-1].lower() if "." in filename else None
    return ext in BINARY_EXTENSIONS or ext in TEXT_EXTENSIONS if ext else False


def is_supported_mime_type(content_type: str) -> bool:
    """
    Check if a MIME type is supported.
    """
    return content_type.lower() in SUPPORTED_MIME_TYPES.keys()


class ContentModel(BaseModel):
    hash: str
    content_type: str
    filename: str
    size: int
    created_at: str
    docling_date: str | None = None
    markdown_date: str | None = None
    attachment_hashes: List[str] = []
    chunk_date: str | None = None
