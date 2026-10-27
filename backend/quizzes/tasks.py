from celery import shared_task
from .generation_jobs import run_generation_job


@shared_task(ignore_result=True)
def run_question_generation(job_id):
    run_generation_job(job_id)
