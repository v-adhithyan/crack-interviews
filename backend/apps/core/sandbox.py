"""Disposable Docker execution for untrusted coding-platform submissions."""

import io
import os
import tarfile
import time

import docker
from django.conf import settings
from docker.errors import DockerException


OUTPUT_LIMIT_BYTES = 1024 * 1024


class SandboxUnavailable(RuntimeError):
    pass


def _archive(files):
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as bundle:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o444
            bundle.addfile(info, io.BytesIO(data))
    archive.seek(0)
    return archive


def _read_container_file(container, path):
    result = container.exec_run(["head", "-c", str(OUTPUT_LIMIT_BYTES + 1), path])
    if result.exit_code != 0:
        return ""
    data = result.output
    if len(data) > OUTPUT_LIMIT_BYTES:
        return data[:OUTPUT_LIMIT_BYTES].decode("utf-8", errors="replace") + "\n[output truncated]"
    return data.decode("utf-8", errors="replace")


def _read_memory(container):
    try:
        return int(_read_container_file(container, "/workspace/memory.txt").strip())
    except (ValueError, DockerException):
        return 0


def run_in_sandbox(files, command, stdin="", timeout_seconds=None):
    """Run one test case in a fresh, networkless, resource-limited container."""
    try:
        client = docker.from_env(timeout=3)
        container = client.containers.create(
            image=settings.CODE_RUNNER_IMAGE,
            command=["sleep", "infinity"],
            user="65534:65534",
            working_dir="/workspace",
            network_disabled=True,
            mem_limit=settings.CODE_MEMORY_LIMIT,
            nano_cpus=int(settings.CODE_CPU_LIMIT * 1_000_000_000),
            pids_limit=settings.CODE_PROCESS_LIMIT,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            tmpfs={
                "/workspace": "rw,nosuid,size=16m,uid=65534,gid=65534",
                "/tmp": "rw,noexec,nosuid,size=16m,uid=65534,gid=65534",
                "/var/tmp": "rw,noexec,nosuid,size=8m,uid=65534,gid=65534",
                "/dev/shm": "rw,noexec,nosuid,size=8m,uid=65534,gid=65534",
            },
            stdin_open=False,
            tty=False,
            labels={"com.crack-interviews.sandbox": "submission"},
        )
        container.put_archive("/opt", _archive({**files, "input.txt": stdin}))
        container.start()
        execution = client.api.exec_create(container.id, ["sh", "-c", command], stdout=False, stderr=False)
        client.api.exec_start(execution["Id"], detach=True)
        deadline = time.monotonic() + (timeout_seconds or settings.CODE_TIMEOUT_SECONDS)
        while True:
            result = client.api.exec_inspect(execution["Id"])
            if not result["Running"]:
                break
            if time.monotonic() >= deadline:
                container.kill()
                raise TimeoutError("Execution timed out.")
            time.sleep(0.05)
        stdout = _read_container_file(container, "/workspace/stdout.txt")
        stderr = _read_container_file(container, "/workspace/stderr.txt")
        memory_kb = _read_memory(container)
        return int(result.get("ExitCode", 1)), stdout, stderr, memory_kb
    except TimeoutError:
        raise
    except DockerException as exc:
        raise SandboxUnavailable(f"Code sandbox is unavailable: {exc}") from exc
    finally:
        if "container" in locals():
            try:
                container.remove(force=True)
            except DockerException:
                pass
        if "client" in locals():
            client.close()

