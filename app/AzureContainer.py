from datetime import datetime
import os
from azure.storage.blob import BlobServiceClient, ContainerClient


class AzureBlobContainer:
    container_client: ContainerClient

    def __init__(self, container_name: str):
        connstr = os.getenv("CONTENT_STORAGE_CONNSTRING")
        if not connstr:
            raise ValueError(
                "CONTENT_STORAGE_CONNSTRING is required. Configure your environment."
            )
        self.blob_service_client = BlobServiceClient.from_connection_string(connstr)
        self.container_client = self.blob_service_client.get_container_client(
            container_name
        )

    def list_blobs(
        self, name_starts_with: str | None = None
    ) -> list[tuple[str, datetime, int, str]]:
        """
        Lists the blob names in the container.

        :return: A list of blobs.
        """
        return [
            (blob.name, blob.creation_time, blob.size, blob.blob_type)
            for blob in self.container_client.list_blobs(
                name_starts_with=name_starts_with
            )
        ]

    def get_bytes(self, blob_name: str) -> bytes | None:
        blob_client = self.container_client.get_blob_client(blob_name)
        if not blob_client.exists():
            return None
        downloaded_blob = blob_client.download_blob()
        return downloaded_blob.readall()

    def set_bytes(self, blob_name: str, blob_bytes: bytes | str) -> None:
        blob_client = self.container_client.get_blob_client(blob_name)
        blob_client.upload_blob(blob_bytes, overwrite=True)

    def exists(self, blob_name: str) -> bool:
        blob_client = self.container_client.get_blob_client(blob_name)
        return blob_client.exists()

    def delete(self, blob_name: str) -> None:
        blob_client = self.container_client.get_blob_client(blob_name)
        blob_client.delete_blob()

    def get_blob_date(self, blob_name: str) -> datetime | None:
        blob_client = self.container_client.get_blob_client(blob_name)
        if not blob_client.exists():
            return None
        blob_properties = blob_client.get_blob_properties()
        return blob_properties.creation_time


def get_content_by_hash_container() -> AzureBlobContainer:
    return AzureBlobContainer("content-by-hash")
