from __future__ import annotations

import json
import logging
from pathlib import PurePosixPath

from plotdas_client.cache import CacheManager
from plotdas_client.models import ImageRecord
from plotdas_client.transport import (
    CancellationToken,
    ProgressCallback,
    ServerTransport,
    TransferProgress,
)

LOGGER = logging.getLogger(__name__)


class ImageService:
    def __init__(self, transport: ServerTransport, cache: CacheManager):
        self.transport = transport
        self.cache = cache

    def fetch(
        self,
        project: str,
        remote_image: str,
        remote_metadata: str | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> ImageRecord:
        local_image, local_metadata = self.cache.paths_for(project, remote_image)
        metadata = self.cache.read_metadata(local_metadata) or {}
        metadata_changed = False
        if remote_metadata:
            raw = self.transport.read_text(remote_metadata)
            try:
                remote_payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"metadata 格式错误: {remote_metadata}: {exc}") from exc
            if remote_payload != metadata:
                metadata = remote_payload
                metadata_changed = True
                self.cache.write_metadata(local_metadata, metadata)
        if not local_image.exists() or metadata_changed:
            LOGGER.info("Downloading image %s", remote_image)
            self.transport.download_file(remote_image, local_image, progress_callback, cancel_token)
        elif progress_callback:
            size = local_image.stat().st_size
            progress_callback(
                TransferProgress(
                    remote_image,
                    size,
                    size,
                    100.0,
                    0.0,
                    0.0,
                    status="cached",
                    is_cached=True,
                )
            )
        return ImageRecord(project, remote_image, remote_metadata, local_image, metadata)

    def fetch_index_record(
        self,
        project: str,
        project_output: str,
        record: dict[str, object],
        progress_callback: ProgressCallback | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> ImageRecord:
        image_path = PurePosixPath(str(record["image_path"]))
        if image_path.is_absolute():
            remote_image = str(image_path)
        else:
            output = PurePosixPath(project_output)
            base = output.parent if output.name == project and image_path.parts[0] == project else output
            remote_image = str(base / image_path)
        metadata_value = record.get("metadata_path")
        remote_metadata = str(metadata_value) if metadata_value else None
        local_image, local_metadata = self.cache.paths_for(project, remote_image)
        cached_metadata = self.cache.read_metadata(local_metadata) or {}
        created_at = record.get("created_at")
        unchanged = (
            cached_metadata.get("created_at") == created_at if created_at else cached_metadata == record
        )
        if local_image.exists() and unchanged:
            LOGGER.debug("Image cache hit without network access: %s", local_image)
            if progress_callback:
                size = local_image.stat().st_size
                progress_callback(
                    TransferProgress(
                        remote_image,
                        size,
                        size,
                        100.0,
                        0.0,
                        0.0,
                        status="cached",
                        is_cached=True,
                    )
                )
            return ImageRecord(project, remote_image, remote_metadata, local_image, cached_metadata)

        metadata = dict(record)
        self.cache.write_metadata(local_metadata, metadata)
        LOGGER.info("Downloading indexed image %s", remote_image)
        self.transport.download_file(remote_image, local_image, progress_callback, cancel_token)
        return ImageRecord(project, remote_image, remote_metadata, local_image, metadata)
