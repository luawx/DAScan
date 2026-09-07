from plotdas_client.models import ImageRecord, PlotRequest

from .image_service import ImageService
from .remote_client import PlotDasRemoteClient


class PlotService:
    def __init__(self, remote: PlotDasRemoteClient, images: ImageService):
        self.remote = remote
        self.images = images

    def preview(self, request: PlotRequest) -> ImageRecord:
        result = self.remote.preview(request)
        return self.images.fetch(request.project, result["image"], result.get("metadata"))
