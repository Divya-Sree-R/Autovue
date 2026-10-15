#!/usr/bin/env python3
"""Control authenticated, loopback-only AutoVue in WSL; never publish a tunnel.

    python3 deploy/local_app.py start
    python3 deploy/local_app.py status
    python3 deploy/local_app.py stop

Credentials and runtime state stay in ignored app_data/funnel. No dependencies
are installed and no cloud SDK is imported. Existing jobs and builds are reused.
"""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import signal
import shutil
import socket
import stat
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = ROOT / "app_data" / "funnel"
ACTIVE_STATUSES = {
    "QUEUED", "DETECTING_TRACKING", "OCR_PROCESSING",
    "TEMPORAL_CONSENSUS", "RENDERING",
}


class ControlError(RuntimeError):
    pass


def private_directory(path: Path) -> None:
    if path.is_symlink():
        raise ControlError(f"Refusing symlink runtime directory: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_uid != os.getuid():
        raise ControlError(f"Runtime directory belongs to another user: {path}")
    path.chmod(0o700)


def secure_read(path: Path) -> str:
    # O_NOFOLLOW protects against replacing the checked path with a symlink.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "r", encoding="utf-8") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise ControlError(f"Refusing unsafe runtime file: {path}")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ControlError(f"Runtime file must be private (chmod 600): {path}")
        return source.read()


def private_write(path: Path, content: str, *, exclusive: bool = False) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
    flags |= os.O_EXCL if exclusive else os.O_TRUNC
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
        metadata = os.fstat(destination.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise ControlError(f"Refusing unsafe runtime file: {path}")
        os.fchmod(destination.fileno(), 0o600)
        destination.write(content)


def read_auth(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in secure_read(path).splitlines():
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key not in {"AUTOVUE_AUTH_USERNAME", "AUTOVUE_AUTH_PASSWORD"} or key in values:
            raise ControlError("Invalid auth.env; use plain KEY=value lines with both credentials.")
        values[key] = value
    username = values.get("AUTOVUE_AUTH_USERNAME", "")
    password = values.get("AUTOVUE_AUTH_PASSWORD", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", username) or len(password) < 24:
        raise ControlError("auth.env requires a valid username and a password of at least 24 characters.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", password):
        raise ControlError("auth.env password must contain only letters, digits, underscores and hyphens.")
    return values


def ensure_auth(state_dir: Path) -> dict[str, str]:
    path = state_dir / "auth.env"
    if not path.exists() and not path.is_symlink():
        private_write(
            path,
            "AUTOVUE_AUTH_USERNAME=autovue\n"
            f"AUTOVUE_AUTH_PASSWORD={secrets.token_urlsafe(32)}\n",
            exclusive=True,
        )
    return read_auth(path)


@contextmanager
def control_lock(state_dir: Path):
    private_directory(state_dir)
    path = state_dir / "control.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+") as lock:
        metadata = os.fstat(lock.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise ControlError("Unsafe controller lock file.")
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def process_identity(pid: int) -> dict | None:
    if not isinstance(pid, int) or pid <= 1:
        return None
    process = Path("/proc") / str(pid)
    try:
        # The executable's comm field may contain spaces or parentheses.
        suffix = (process / "stat").read_text().rsplit(")", 1)[1].split()
        if suffix[0] == "Z":
            return None
        return {
            "pid": pid,
            "uid": process.stat().st_uid,
            "start_ticks": suffix[19],
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "command": (process / "cmdline").read_bytes().rstrip(b"\0").decode().split("\0"),
            "process_group": int(suffix[2]),
            "session": int(suffix[3]),
        }
    except (OSError, ValueError, IndexError, UnicodeError):
        return None


def read_state(state_dir: Path) -> dict | None:
    path = state_dir / "app.json"
    try:
        state = json.loads(secure_read(path))
    except FileNotFoundError:
        return None
    except (ValueError, TypeError) as exc:
        raise ControlError("Invalid app.json; refusing to manage an unidentified process.") from exc
    if not isinstance(state, dict) or not isinstance(state.get("process"), dict):
        raise ControlError("Invalid controller state; refusing to manage an unidentified process.")
    return state


def owned_process(state: dict | None) -> bool:
    if state is None:
        return False
    expected = state.get("process", {})
    pid = expected.get("pid")
    current = process_identity(pid)
    return bool(
        current is not None and current == expected and current["uid"] == os.getuid()
        and current["process_group"] == pid and current["session"] == pid
        and current["command"][1:4] == ["-B", "-m", "uvicorn"]
        and "app.backend.main:app" in current["command"]
    )


def request_json(url: str, auth: dict[str, str], *, timeout: float = 5) -> dict:
    credentials = f"{auth['AUTOVUE_AUTH_USERNAME']}:{auth['AUTOVUE_AUTH_PASSWORD']}"
    token = base64.b64encode(credentials.encode()).decode()
    request = Request(url, headers={"Authorization": f"Basic {token}"})
    # Explicitly ignore HTTP_PROXY for the local controller.
    from urllib.request import ProxyHandler, build_opener
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        if response.status != 200:
            raise ControlError(f"Local API returned HTTP {response.status}.")
        return json.load(response)


def check_port(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        # Match uvicorn's reusable listening socket: recent browser/API
        # connections may leave TIME_WAIT entries after a clean shutdown.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise ControlError(f"127.0.0.1:{port} is occupied; no existing process was stopped.") from exc


def preflight(root: Path, environment: dict[str, str]) -> None:
    main_python = Path(environment["AUTOVUE_MAIN_PYTHON"])
    paddle_python = Path(environment["AUTOVUE_PADDLE_PYTHON"])
    for interpreter in (main_python, paddle_python):
        if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
            raise ControlError(f"Existing Python environment missing: {interpreter}")
    frontend = Path(environment["AUTOVUE_FRONTEND_DIST"])
    index = frontend / "index.html"
    if not index.is_file() or index.is_symlink():
        raise ControlError("Build React first: cd app/frontend && npm run build")
    for relative in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', index.read_text()):
        asset = frontend / relative.lstrip("/")
        if not asset.is_file() or asset.is_symlink() or not asset.resolve().is_relative_to(frontend.resolve()):
            raise ControlError(f"Frontend build asset missing or unsafe: {relative}")
    assets = (
        Path(environment.get("AUTOVUE_VEHICLE_MODEL_PATH", root / "yolo11n.pt")),
        Path(environment.get("AUTOVUE_PLATE_MODEL_PATH", root / "experiments/detector_benchmark/yolo11n/weights/best.pt")),
    )
    for asset in assets:
        if not asset.is_file():
            raise ControlError(f"Frozen model asset missing: {asset}")
    if not shutil.which("ffmpeg"):
        raise ControlError("Existing ffmpeg is required for browser video playback.")
    checks = (
        (main_python, "from deploy.prepare import verify; verify()"),
        (main_python, "import fastapi, uvicorn, cv2, torch, ultralytics; "
         "assert torch.cuda.is_available(), 'The existing NVIDIA GPU is unavailable'; "
         "print(torch.cuda.get_device_name(0))"),
        (paddle_python, "import paddle, paddleocr; "
         "assert paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0, "
         "'The existing Paddle CUDA GPU is unavailable'"),
    )
    for interpreter, code in checks:
        checked = subprocess.run(
            [str(interpreter), "-B", "-c", code], cwd=root, env=environment,
            capture_output=True, text=True, timeout=120,
        )
        if checked.returncode:
            # No credentials are present in the check's command or diagnostics.
            raise ControlError(f"Existing environment/GPU check failed ({interpreter}):\n{checked.stderr[-3000:]}")


def environment_for(root: Path, jobs_root: Path, auth: dict[str, str], *, port: int = 8080) -> dict[str, str]:
    environment = os.environ.copy()
    python_path = [str(root / "src"), str(root)]
    if environment.get("PYTHONPATH"):
        python_path.append(environment["PYTHONPATH"])
    environment.update(auth)
    environment.update({
        "AUTOVUE_REQUIRE_AUTH": "1",
        "AUTOVUE_PUBLIC_MODE": environment.get("AUTOVUE_PUBLIC_MODE", "0"),
        "AUTOVUE_LOCAL_HOSTS": f"127.0.0.1:{port},localhost:{port}",
        "AUTOVUE_CORS_ORIGINS": "",
        "AUTOVUE_FRONTEND_DIST": str(root / "app/frontend/dist"),
        "AUTOVUE_MAIN_PYTHON": str(root / ".venv/bin/python"),
        "AUTOVUE_PADDLE_PYTHON": str(root / ".venv_paddleocr/bin/python"),
        "AUTOVUE_JOBS_ROOT": str(jobs_root),
        "PYTHONPATH": os.pathsep.join(python_path),
        "PYTHONUNBUFFERED": "1",
    })
    return environment


def start(state_dir: Path, *, port: int, jobs_root: Path, timeout: float = 45) -> dict:
    public_configuration = {
        key: os.environ.get(key, "0" if key == "AUTOVUE_PUBLIC_MODE" else "")
        for key in ("AUTOVUE_PUBLIC_MODE", "AUTOVUE_PUBLIC_HOST", "AUTOVUE_PUBLIC_ORIGIN")
    }
    state = read_state(state_dir)
    if owned_process(state):
        if state["port"] != port or state["jobs_root"] != str(jobs_root) or state.get("public_configuration") != public_configuration:
            raise ControlError("AutoVue is already running with different settings; stop it first.")
        print(f"AutoVue already running at {state['url']}; credentials: {state_dir / 'auth.env'}")
        return state
    if state is not None and process_identity(state["process"].get("pid")) is not None:
        raise ControlError("Stored PID belongs to a different process; refusing to overwrite controller state.")
    check_port(port)
    auth = ensure_auth(state_dir)
    environment = environment_for(ROOT, jobs_root, auth, port=port)
    preflight(ROOT, environment)
    if jobs_root.is_symlink():
        raise ControlError("Refusing symlink job storage.")
    jobs_root.mkdir(parents=True, exist_ok=True)
    log_path = state_dir / "app.log"
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a") as log:
        if os.fstat(log.fileno()).st_uid != os.getuid():
            raise ControlError("App log belongs to another user.")
        os.fchmod(log.fileno(), 0o600)
        process = subprocess.Popen(
            [environment["AUTOVUE_MAIN_PYTHON"], "-B", "-m", "uvicorn", "app.backend.main:app",
             "--host", "127.0.0.1", "--port", str(port), "--workers", "1", "--no-proxy-headers"],
            cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
    # Capture identity immediately; a successful Popen has completed exec.
    identity = process_identity(process.pid)
    state = {
        "process": identity, "port": port, "url": f"http://127.0.0.1:{port}",
        "jobs_root": str(jobs_root), "log": str(log_path), "started_at": time.time(),
        "public_configuration": public_configuration,
    }
    if identity is None or not owned_process(state):
        raise ControlError(f"Backend exited before startup; inspect {log_path}")
    private_write(state_dir / "app.json", json.dumps(state, indent=2) + "\n")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not owned_process(state):
            raise ControlError(f"Backend failed to start; inspect {log_path}")
        try:
            health = request_json(state["url"] + "/health", auth)
            jobs = request_json(state["url"] + "/api/jobs", auth)
            if health.get("service") == "AutoVue API" and isinstance(jobs.get("jobs"), list):
                print(f"AutoVue started at {state['url']} (local only).")
                print(f"Private login: {state_dir / 'auth.env'}; log: {log_path}")
                return state
        except (OSError, ValueError, HTTPError, URLError):
            pass
        time.sleep(0.25)
    # Keep controller identity for a safe subsequent stop/debug; no PID guessing.
    raise ControlError(f"Startup timed out; inspect {log_path}, then run the stop command.")


def status(state_dir: Path) -> dict:
    state = read_state(state_dir)
    if not owned_process(state):
        result = {"running": False, "controller_state": "stale" if state else "absent"}
    else:
        result = {"running": True, "pid": state["process"]["pid"], "url": state["url"], "log": state["log"]}
        try:
            jobs = request_json(state["url"] + "/api/jobs", read_auth(state_dir / "auth.env"))
            result["active_jobs"] = [job["job_id"] for job in jobs["jobs"] if job.get("status") in ACTIVE_STATUSES]
            result["api_healthy"] = True
        except (OSError, ValueError, KeyError, HTTPError, URLError, ControlError):
            result["api_healthy"] = False
    print(json.dumps(result, indent=2))
    return result


def stop(state_dir: Path, *, force: bool = False, timeout: float = 30) -> None:
    state = read_state(state_dir)
    if not owned_process(state):
        print("AutoVue controller has no running process; no process was stopped.")
        return
    if not force:
        try:
            jobs = request_json(state["url"] + "/api/jobs", read_auth(state_dir / "auth.env"))
            active = [job.get("job_id") for job in jobs["jobs"] if job.get("status") in ACTIVE_STATUSES]
        except (OSError, ValueError, KeyError, HTTPError, URLError) as exc:
            raise ControlError("Cannot verify idle GPU state; retry after recovery or explicitly use stop --force.") from exc
        if active:
            raise ControlError(f"HTTP 409: active analysis {active}; wait for completion or explicitly use stop --force.")
    if not owned_process(state):
        raise ControlError("Process identity changed; no process was stopped.")
    os.killpg(state["process"]["pid"], signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not owned_process(state):
            print("AutoVue stopped. Jobs, results, credentials and logs are preserved.")
            return
        time.sleep(0.1)
    if force and owned_process(state):
        os.killpg(state["process"]["pid"], signal.SIGKILL)
        print("AutoVue force-stopped. Check interrupted job logs before starting another analysis.")
        return
    raise ControlError("Graceful shutdown timed out; inspect app.log or explicitly use stop --force.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    begin = commands.add_parser("start", help="Start the authenticated local production app")
    begin.add_argument("--port", type=int, default=8080)
    begin.add_argument("--jobs-root", type=Path, default=ROOT / "app_data/jobs")
    commands.add_parser("status", help="Show owned process/API/GPU-job status")
    end = commands.add_parser("stop", help="Stop only this controller's process, preserving storage")
    end.add_argument("--force", action="store_true", help="Explicitly interrupt active analysis or an unresponsive backend")
    args = parser.parse_args(argv)
    if args.command == "start" and not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    try:
        with control_lock(args.state_dir.expanduser().absolute()):
            if args.command == "start":
                start(args.state_dir.expanduser().absolute(), port=args.port, jobs_root=args.jobs_root.expanduser().absolute())
            elif args.command == "stop":
                stop(args.state_dir.expanduser().absolute(), force=args.force)
            else:
                status(args.state_dir.expanduser().absolute())
        return 0
    except (ControlError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"AutoVue: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
