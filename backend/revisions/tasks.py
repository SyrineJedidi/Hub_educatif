from celery import shared_task
from .ai.jobs import run_job


@shared_task(ignore_result=True)
def run_ai_job(job_id):
    run_job(job_id)
