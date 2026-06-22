import re
import subprocess
import tempfile
import time
from pathlib import Path

from django.conf import settings

from .models import Submission, TestCaseResult


CLASS_PATTERN = re.compile(r"(?:public\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)")
PUBLIC_CLASS_PATTERN = re.compile(r"public\s+class\s+([A-Za-z_][A-Za-z0-9_]*)")


def normalize_output(value):
    return value.replace("\r\n", "\n").strip()


def class_name_for_java(code):
    public_match = PUBLIC_CLASS_PATTERN.search(code)
    if public_match:
        return public_match.group(1)

    class_names = CLASS_PATTERN.findall(code)
    for preferred in ("Main", "Solution"):
        if preferred in class_names:
            return preferred
    return class_names[0] if class_names else "Main"


def compile_java(code):
    temp_dir = tempfile.TemporaryDirectory()
    class_name = class_name_for_java(code)
    source_path = Path(temp_dir.name) / f"{class_name}.java"
    source_path.write_text(code, encoding="utf-8")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [settings.JAVAC_EXECUTABLE, "--release", str(settings.JAVA_RELEASE), str(source_path)],
            text=True,
            capture_output=True,
            timeout=settings.COMPILE_TIMEOUT_SECONDS,
            check=False,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if completed.returncode == 0:
            return temp_dir, class_name, "", elapsed_ms
        error = completed.stderr or completed.stdout
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        error = exc.stderr or exc.stdout or "Compilation timed out."

    if isinstance(error, bytes):
        error = error.decode("utf-8", errors="replace")
    if error:
        temp_dir.cleanup()
        return None, class_name, error, elapsed_ms
    temp_dir.cleanup()
    return None, class_name, "Compilation failed.", elapsed_ms


def run_process_for_test(submission, test_case, java_context=None):
    if submission.language == Submission.Language.JAVA:
        temp_dir, class_name = java_context
        command = [settings.JAVA_EXECUTABLE, "-cp", temp_dir.name, class_name]
    else:
        command = [settings.PYTHON_EXECUTABLE, "-c", submission.code]

    return subprocess.run(
        command,
        input=test_case.stdin,
        text=True,
        capture_output=True,
        timeout=settings.CODE_TIMEOUT_SECONDS,
        check=False,
    )


def run_submission(submission, test_cases):
    total_start = time.perf_counter()
    passed_count = 0
    final_status = Submission.Status.ACCEPTED
    combined_stdout = []
    combined_stderr = []
    test_cases = list(test_cases)
    java_temp_dir = None
    java_class_name = None

    if submission.language == Submission.Language.JAVA:
        java_temp_dir, java_class_name, compile_error, compile_ms = compile_java(submission.code)
        if compile_error:
            final_status = Submission.Status.RUNTIME_ERROR
            for test_case in test_cases:
                TestCaseResult.objects.create(
                    submission=submission,
                    test_case=test_case,
                    status=final_status,
                    stdout="",
                    stderr=compile_error,
                    expected_output=test_case.expected_output,
                    execution_time_ms=compile_ms,
                )
            submission.status = final_status
            submission.stdout = ""
            submission.stderr = compile_error
            submission.execution_time_ms = int((time.perf_counter() - total_start) * 1000)
            submission.passed_count = 0
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

    try:
        for test_case in test_cases:
            started = time.perf_counter()
            try:
                completed = run_process_for_test(
                    submission,
                    test_case,
                    java_context=(java_temp_dir, java_class_name) if java_temp_dir else None,
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
    finally:
        if java_temp_dir:
            java_temp_dir.cleanup()

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
