import datetime
import json
from typing import AnyStr, Sequence

from google.cloud.storage import Bucket

from thor.orbits import Orbits
from thor.taskqueue.tasks import Task


class JobManifest:
    """
    A manifest which lists all the orbit IDs and task IDs associated with a
    particular job. This class is serialized into a string and stored in the
    Google Cloud Storage bucket for a job. It can be retrieved to iterate over
    tasks.
    """

    def __init__(self, creation_time, job_id, orbit_ids, task_ids):
        """
        Low-level constructor for a JobManifest.

        Use the create classmethod instead.
        """
        self.creation_time = creation_time
        self.job_id = job_id
        self.orbit_ids = orbit_ids
        self.task_ids = task_ids

    @classmethod
    def create(cls, job_id: str):
        """
        Create a new empty JobManifest with the given job ID.

        Parameters
        ----------
        job_id : str
            Identifier for the job.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        return JobManifest(creation_time=now, job_id=job_id, orbit_ids=[], task_ids=[])

    def append(self, orbit_id, task_id):
        """
        Add an orbit ID and task ID to the manifest.

        The orbit ID should be the orbit being handled in the given task. If the
        task handles multiple orbits, orbit_id should be a list of orbit IDs.
        """
        self.orbit_ids.append(orbit_id)
        self.task_ids.append(task_id)

    def to_str(self) -> str:
        """
        JSON-serializes the JobManifest as a string.
        """
        return json.dumps(
            {
                "job_id": self.job_id,
                "creation_time": self.creation_time.isoformat(),
                "orbit_ids": self.orbit_ids,
                "task_ids": self.task_ids,
            }
        )

    @classmethod
    def from_str(cls, data: AnyStr) -> "JobManifest":
        """
        Creates a JobManifest from a string JSON representation, as created by
        JobManifest.to_str.
        """
        as_dict = json.loads(data)
        as_dict["creation_time"] = datetime.datetime.fromisoformat(
            as_dict["creation_time"]
        )
        return cls(**as_dict)


def upload_job_manifest(bucket: Bucket, manifest: JobManifest):
    """
    Upload a JobManifest to a bucket. It gets stored in
    BUCKET/thor_jobs/v1/job-{job_id}/manifest.json

    Parameters
    ----------
    bucket : google.cloud.storage.Bucket
        The GCS bucket where job data is stored.
    manifest : thor.taskqueue.JobManifest
        The manifest to upload.
    """
    path = f"thor_jobs/v1/job-{manifest.job_id}/manifest.json"
    bucket.blob(path).upload_from_string(manifest.to_str())


def download_job_manifest(bucket: Bucket, job_id: str) -> JobManifest:
    """
    Download the JobManifest associated with job_id in given bucket.

    Parameters
    ----------
    bucket : google.cloud.storage.Bucket
        The GCS bucket where job data is stored.
    job_id : str
        The ID of the job.

    Returns
    -------
    JobManifest
    """
    path = f"thor_jobs/v1/job-{job_id}/manifest.json"
    as_str = bucket.blob(path).download_as_string()
    return JobManifest.from_str(as_str)
