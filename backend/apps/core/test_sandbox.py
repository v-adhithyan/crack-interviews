from django.test import SimpleTestCase

from .sandbox import run_in_sandbox


class SubmissionSandboxTests(SimpleTestCase):
    def test_submission_container_has_no_network(self):
        code = (
            "import socket\n"
            "try:\n"
            "    socket.create_connection(('1.1.1.1', 53), timeout=1)\n"
            "except OSError:\n"
            "    print('network-blocked')\n"
            "else:\n"
            "    raise SystemExit('network was reachable')\n"
        )
        status, stdout, stderr, _ = run_in_sandbox(
            {"main.py": code},
            "python /opt/main.py > /workspace/stdout.txt 2> /workspace/stderr.txt",
        )

        self.assertEqual(status, 0, stderr)
        self.assertEqual(stdout.strip(), "network-blocked")

    def test_submission_timeout_kills_the_container(self):
        with self.assertRaisesRegex(TimeoutError, "timed out"):
            run_in_sandbox(
                {"main.py": "while True: pass"},
                "python /opt/main.py > /workspace/stdout.txt 2> /workspace/stderr.txt",
                timeout_seconds=1,
            )
