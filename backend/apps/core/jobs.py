from django_q.tasks import async_task


def enqueue_background_job(task_path, *args, **kwargs):
    return async_task(task_path, *args, **kwargs)
