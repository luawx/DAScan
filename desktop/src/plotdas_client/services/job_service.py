from plotdas_client.models import Job, PlotRequest

from .remote_client import PlotDasRemoteClient


class JobService:
    def __init__(self, remote: PlotDasRemoteClient):
        self.remote = remote

    def create_and_start(self, request: PlotRequest) -> Job:
        created = self.remote.create_job(request)
        job_id = created["job_id"]
        return Job.from_dict(self.remote.start_job(job_id))

    def list_jobs(self) -> list[Job]:
        return [Job.from_dict(item) for item in self.remote.list_jobs()]

    def cancel(self, job_id: str) -> Job:
        return Job.from_dict(self.remote.cancel_job(job_id))
