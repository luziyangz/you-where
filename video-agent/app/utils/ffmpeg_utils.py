import subprocess


def run_media_command(args: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    if not args:
        msg = "command arguments are required"
        raise ValueError(msg)
    return subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
