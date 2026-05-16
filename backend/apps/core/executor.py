import subprocess
import time

from django.conf import settings

from .models import Submission, TestCaseResult


def normalize_output(value):
    return value.replace("\r\n", "\n").strip()


def run_submission(submission, test_cases):
    total_start = time.perf_counter()
    passed_count = 0
    final_status = Submission.Status.ACCEPTED
    combined_stdout = []
    combined_stderr = []
    test_cases = list(test_cases)

    for test_case in test_cases:
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                [settings.PYTHON_EXECUTABLE, "-c", submission.code],
                input=test_case.stdin,
                text=True,
                capture_output=True,
                timeout=settings.CODE_TIMEOUT_SECONDS,
                check=False,
            )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            stdout = completed.stdout
            stderr = completed.stderr

            if completed.returncode != 0:
                status = Submission.Status.RUNTIME_ERROR
            elif normalize_output(stdout) == normalize_output(test_case.expected_output):
                status = Submission.Status.ACCEPTED
                passed_count += 1
            else:
                status = Submission.Status.WRONG_ANSWER
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            stdout = exc.stdout or ""
            stderr = exc.stderr or "Execution timed out."
            status = Submission.Status.TIME_LIMIT_EXCEEDED

        TestCaseResult.objects.create(
            submission=submission,
            test_case=test_case,
            status=status,
            stdout=stdout,
            stderr=stderr,
            expected_output=test_case.expected_output,
            execution_time_ms=elapsed_ms,
        )
        combined_stdout.append(stdout)
        combined_stderr.append(stderr)

        if status != Submission.Status.ACCEPTED and final_status == Submission.Status.ACCEPTED:
            final_status = status

    submission.status = final_status
    submission.stdout = "\n".join(part for part in combined_stdout if part)
    submission.stderr = "\n".join(part for part in combined_stderr if part)
    submission.execution_time_ms = int((time.perf_counter() - total_start) * 1000)
    submission.passed_count = passed_count
    submission.total_count = len(test_cases)
    submission.save(update_fields=[
        "status",
        "stdout",
        "stderr",
        "execution_time_ms",
        "passed_count",
        "total_count",
    ])
    return submission
