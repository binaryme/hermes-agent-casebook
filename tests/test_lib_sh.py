import os
import subprocess
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent / "harness" / "lib.sh"

FAKE_DOCKER = """#!/usr/bin/env bash
printf '%s\\n' "$@" > "$FAKE_DOCKER_ARGS"
exit "${FAKE_DOCKER_STATUS:-0}"
"""


class LibShellCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        bin_dir = Path(self.temp.name) / "bin"
        bin_dir.mkdir()
        docker = bin_dir / "docker"
        docker.write_text(FAKE_DOCKER, encoding="utf-8")
        docker.chmod(0o755)
        self.args_file = Path(self.temp.name) / "docker-args.txt"
        self.env = {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_DOCKER_ARGS": str(self.args_file),
            "HERMES_IMAGE": "example/hermes@sha256:abc",
        }

    def call(self, snippet, **extra_env):
        env = dict(self.env, **extra_env)
        env = {key: value for key, value in env.items() if value is not None}
        return subprocess.run(
            ["bash", "-c", f'source "{LIB}"; {snippet}'],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def docker_args(self):
        return self.args_file.read_text(encoding="utf-8").splitlines()


class HermesExecTests(LibShellCase):
    def test_runs_without_network_by_default(self):
        completed = self.call("hermes_exec version --json")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            self.docker_args(),
            ["run", "--rm", "--label", "casebook=repro", "--network", "none", "example/hermes@sha256:abc", "version", "--json"],
        )

    def test_network_flag_is_dropped_when_requested(self):
        completed = self.call("hermes_exec version", HERMES_EXEC_NETWORK="1")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            self.docker_args(),
            ["run", "--rm", "--label", "casebook=repro", "example/hermes@sha256:abc", "version"],
        )

    def test_only_the_value_one_drops_the_network_flag(self):
        self.call("hermes_exec version", HERMES_EXEC_NETWORK="0")
        self.assertIn("none", self.docker_args())

    def test_fails_without_an_image(self):
        completed = self.call("hermes_exec version", HERMES_IMAGE=None)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("HERMES_IMAGE", completed.stderr)
        self.assertFalse(self.args_file.exists())

    def test_docker_failure_status_propagates(self):
        completed = self.call("hermes_exec version", FAKE_DOCKER_STATUS="9")
        self.assertEqual(completed.returncode, 9)


class HermesExecDataTests(LibShellCase):
    def test_mounts_the_host_directory_at_opt_data(self):
        completed = self.call('hermes_exec_data "/tmp/host dir" prompt-size --json')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            self.docker_args(),
            [
                "run", "--rm", "--label", "casebook=repro", "--network", "none",
                "-v", "/tmp/host dir:/opt/data",
                "example/hermes@sha256:abc", "prompt-size", "--json",
            ],
        )

    def test_network_flag_is_dropped_when_requested(self):
        self.call("hermes_exec_data /tmp/d version", HERMES_EXEC_NETWORK="1")
        self.assertNotIn("--network", self.docker_args())


class ShellHelpersTests(LibShellCase):
    def test_hermes_shell_is_a_non_login_bash(self):
        completed = self.call("hermes_shell 'command -v python3'")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            self.docker_args(),
            [
                "run", "--rm", "--label", "casebook=repro", "--network", "none",
                "--entrypoint", "bash",
                "example/hermes@sha256:abc", "-c", "command -v python3",
            ],
        )

    def test_hermes_login_shell_adds_the_login_flag(self):
        completed = self.call("hermes_login_shell 'command -v python3'")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            self.docker_args(),
            [
                "run", "--rm", "--label", "casebook=repro", "--network", "none",
                "--entrypoint", "bash",
                "example/hermes@sha256:abc", "-l", "-c", "command -v python3",
            ],
        )


class ObservedTests(LibShellCase):
    def test_prints_the_marker_line(self):
        completed = self.call("observed alpha-only")
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "OBSERVED=alpha-only\n")

    def test_accepts_numeric_tokens(self):
        completed = self.call("observed 401")
        self.assertEqual(completed.stdout, "OBSERVED=401\n")

    def test_rejects_tokens_that_are_not_lowercase_kebab_case(self):
        for bad in ("Alpha", "alpha_only", "alpha only", "-alpha", "alpha-", "a--b", ""):
            with self.subTest(token=bad):
                completed = self.call(f"observed '{bad}'")
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(completed.stdout, "")

    def test_rejects_a_missing_argument(self):
        completed = self.call("observed")
        self.assertNotEqual(completed.returncode, 0)


class RequireEnvTests(LibShellCase):
    def test_passes_when_all_are_set(self):
        completed = self.call("require_env FIRST SECOND", FIRST="1", SECOND="2")
        self.assertEqual(completed.returncode, 0)

    def test_names_every_missing_variable(self):
        completed = self.call("require_env FIRST SECOND THIRD", FIRST="1")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("SECOND", completed.stderr)
        self.assertIn("THIRD", completed.stderr)
        self.assertNotIn("FIRST", completed.stderr)

    def test_empty_value_counts_as_unset(self):
        completed = self.call("require_env FIRST", FIRST="")
        self.assertNotEqual(completed.returncode, 0)


class StrictModeTests(LibShellCase):
    def test_sourcing_enables_strict_mode(self):
        completed = self.call('echo "$-"; set -o | grep pipefail')
        self.assertIn("e", completed.stdout.splitlines()[0])
        self.assertIn("u", completed.stdout.splitlines()[0])
        self.assertIn("on", completed.stdout.splitlines()[1])


if __name__ == "__main__":
    unittest.main()
