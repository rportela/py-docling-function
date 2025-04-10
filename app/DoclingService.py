from email import message_from_bytes, policy
from email.message import EmailMessage
from io import BytesIO
from docling_core.types.io import DocumentStream
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.labels import DocItemLabel
from docling.document_converter import DocumentConverter

from app.AzureContainer import AzureBlobContainer, get_content_by_hash_container
from app.ContentModel import SUPPORTED_MIME_TYPES, ContentModel, is_supported_mime_type

from docling_core.types.doc.document import DoclingDocument
from app.docling_add_doc import docling_add_doc


class DoclingService:

    _converter: DocumentConverter
    _blobs: AzureBlobContainer

    def __init__(self) -> None:
        self._converter = DocumentConverter()
        self._blobs = get_content_by_hash_container()

    def _process_text_content(
        self, content_bytes: bytes, filename: str, encoding: str = "utf-8"
    ) -> DoclingDocument:
        """
        Process text content and convert it to a DoclingDocument.
        """
        doc = DoclingDocument(name=filename)
        content_text = content_bytes.decode(encoding, errors="replace")
        doc.add_text(label=DocItemLabel("text"), text=content_text)
        return doc

    def _process_generic_content(
        self, content_bytes: bytes, filename: str
    ) -> DoclingDocument:
        """
        Process generic content and convert it to a DoclingDocument.
        """
        stream = DocumentStream(name=filename, stream=BytesIO(content_bytes))
        return self._converter.convert(stream).document

    def _process_email_singlepart(
        self, msg: EmailMessage, filename: str
    ) -> DoclingDocument:
        """
        Process a single-part email message and convert it to a DoclingDocument.
        """
        payload: bytes = msg.get_payload(decode=True)  # type: ignore
        content_type = msg.get_content_type()
        filename = msg.get_filename() or filename
        encoding = msg.get_content_charset() or "utf-8"
        return self._process(payload, content_type, filename, encoding)

    def _process_email_multipart(
        self, msg: EmailMessage, filename: str
    ) -> DoclingDocument:
        """
        Process a multipart email and convert each part to a DoclingDocument.
        """
        doc = DoclingDocument(name=msg.get_filename() or filename)
        for part in msg.walk():
            part_bytes: bytes = part.get_payload(decode=True)  # type: ignore
            content_type = part.get_content_type()
            encoding = part.get_content_charset() or "utf-8"
            if not is_supported_mime_type(content_type) or not part_bytes:
                continue
            part_filename = part.get_filename()
            if not part_filename:
                part_filename = (
                    f"attachment{SUPPORTED_MIME_TYPES.get(content_type, '.bin')}"
                )
            part_docling = self._process(
                part_bytes, content_type, part_filename, encoding
            )
            docling_add_doc(doc, part_docling)
        return doc

    def _process_email(self, original_bytes: bytes, filename: str) -> DoclingDocument:
        """
        Convert email content to DoclingDocument format.
        """
        msg = message_from_bytes(
            original_bytes, policy=policy.default, _class=EmailMessage
        )
        if msg.is_multipart():
            return self._process_email_multipart(msg, filename)
        else:
            return self._process_email_singlepart(msg, filename)

    def _process(
        self,
        content_bytes: bytes,
        content_type: str,
        filename: str,
        encoding: str = "utf-8",
    ) -> DoclingDocument:
        """
        Process the content and convert it to a DoclingDocument.
        """
        if content_type == "message/rfc822":
            return self._process_email(content_bytes, filename)
        elif content_type == "text/plain":
            return self._process_text_content(content_bytes, filename, encoding)
        else:
            return self._process_generic_content(content_bytes, filename)

    def get_docling(
        self,
        model: ContentModel,
        original_bytes: bytes,
        overwrite: bool = False,
        attempt: int = 0,
    ) -> DoclingDocument:
        """
        Process the original bytes and convert them to a DoclingDocument.
        """
        blob_name = f"{model.hash}/docling.json"
        docling_date = self._blobs.get_blob_date(blob_name)
        if docling_date is None or overwrite:
            docling = self._process(original_bytes, model.content_type, model.filename)
            self._blobs.set_bytes(blob_name, docling.model_dump_json().encode("utf-8"))
        else:
            docling_bytes = self._blobs.get_bytes(blob_name)
            if docling_bytes is None:
                if attempt > 0:
                    raise ValueError(
                        f"Docling content not found for hash: {model.hash}"
                    )
                else:
                    return self.get_docling(model, original_bytes, True, attempt + 1)
            else:
                try:
                    docling = DoclingDocument.model_validate_json(
                        docling_bytes.decode("utf-8")
                    )
                except Exception as e:
                    if attempt > 0:
                        raise e
                    else:
                        return self.get_docling(
                            model, original_bytes, True, attempt + 1
                        )
        return docling
