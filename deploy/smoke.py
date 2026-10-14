#!/usr/bin/env python3
r"""Exercise a local or public AutoVue deployment without changing its results.

Example:
    python deploy/smoke.py --url http://127.0.0.1:8000 --video sample.mp4
    python deploy/smoke.py --url https://example.modal.run --video sample.mp4 \
        --inference --report /tmp/autovue-public-smoke.json

Supply optional HTTP Basic credentials through AUTOVUE_AUTH_USERNAME and
AUTOVUE_AUTH_PASSWORD. The uploaded job is retained for review, even on failure.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib.parse import quote, urlsplit

import httpx


ACTIVE_STATUSES = {
    "QUEUED", "DETECTING_TRACKING", "OCR_PROCESSING",
    "TEMPORAL_CONSENSUS", "RENDERING",
}
EVIDENCE_STATUSES = {
    "VERIFIED_FULL", "CORROBORATED_FRAGMENT", "NEEDS_REVIEW", "REJECTED",
}
SUMMARY_FIELDS = {
    "raw_tracker_ids", "selected_ocr_crops", "conservative_clusters",
    "parser_valid_crop_predictions", "clusters_with_complete_candidate",
    "unique_selected_candidate_strings", "verified_full",
    "corroborated_fragment", "needs_review", "rejected",
}


class SmokeFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Smoke:
    def __init__(self, client: httpx.Client, report: dict[str, Any]) -> None:
        self.client = client
        self.report = report

    def passed(self, name: str, **details: Any) -> None:
        self.report["checks"].append({"name": name, "passed": True, **details})
        print(f"PASS {name}", flush=True)

    def response(self, method: str, path: str, expected: int = 200, **kwargs: Any) -> httpx.Response:
        response = self.client.request(method, path, **kwargs)
        require(
            response.status_code == expected,
            f"{method} {path}: expected {expected}, received {response.status_code}",
        )
        return response

    def json(self, method: str, path: str, expected: int = 200, **kwargs: Any) -> Any:
        response = self.response(method, path, expected, **kwargs)
        try:
            return response.json()
        except ValueError as exc:
            raise SmokeFailure(f"{method} {path}: response is not JSON") from exc

    def job_ids(self) -> set[str]:
        data = self.json("GET", "/api/jobs")
        require(isinstance(data, dict) and isinstance(data.get("jobs"), list), "Invalid jobs list")
        return {item["job_id"] for item in data["jobs"]}

    def initial_checks(self, authenticated: bool) -> None:
        health = self.json("GET", "/health")
        require(health.get("status") == "ok" and health.get("service") == "AutoVue API", "Unhealthy API")
        self.passed("health", response=health)

        if authenticated:
            for path in ("/", "/api/jobs"):
                response = self.response("GET", path, 401, auth=None)
                require("basic" in response.headers.get("www-authenticate", "").lower(), "Missing Basic auth challenge")
            self.response(
                "POST", "/api/jobs", 403,
                headers={"Origin": "https://untrusted.invalid"},
                files={"file": ("smoke.txt", b"invalid", "text/plain")},
            )
            self.passed("authentication and cross-origin mutation protection")

        for route in ("/", "/analyze", "/results", "/evidence", "/evaluation", "/system"):
            response = self.response("GET", route)
            require("text/html" in response.headers.get("content-type", ""), f"Frontend missing at {route}")
            require('id="root"' in response.text, f"React root missing at {route}")
            for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', response.text):
                asset_response = self.response("GET", asset)
                require(bool(asset_response.content), f"Empty frontend asset: {asset}")
        self.passed("frontend assets and all SPA routes")

        before = self.job_ids()
        for label, filename, content, content_type, expected in (
            ("empty", "smoke-empty.mp4", b"", "video/mp4", 400),
            ("corrupt", "smoke-corrupt.mp4", b"not an MP4 video", "video/mp4", 422),
            ("unsupported", "smoke.txt", b"not a video", "text/plain", 415),
        ):
            self.response("POST", "/api/jobs", expected, files={"file": (filename, content, content_type)})
            after = self.job_ids()
            require(after == before, f"{label} upload changed job workspaces ({len(before)} -> {len(after)})")
            self.passed(f"reject {label} upload and clean workspace", jobs_before=len(before), jobs_after=len(after))

    def video_range(self, job_id: str, kind: str) -> None:
        path = f"/api/jobs/{job_id}/video/{kind}"
        with self.client.stream("GET", path, headers={"Range": "bytes=0-1023"}) as response:
            require(response.status_code == 206, f"{kind} playback: expected 206, received {response.status_code}")
            require("video/mp4" in response.headers.get("content-type", ""), f"{kind}: invalid media type")
            content_range = response.headers.get("content-range", "")
            require(re.fullmatch(r"bytes 0-\d+/\d+", content_range) is not None, f"{kind}: invalid Content-Range")
            content = bytearray()
            for chunk in response.iter_bytes(chunk_size=1024):
                content.extend(chunk)
                require(len(content) <= 1024, f"{kind}: server ignored the requested range")
            require(0 < len(content) <= 1024, f"{kind}: range request returned an invalid body")
        self.passed(f"{kind} video range playback", content_range=content_range, bytes=len(content))

    def upload(self, video: Path) -> str:
        before = self.job_ids()
        with video.open("rb") as source:
            job = self.json("POST", "/api/jobs", 201, files={"file": (video.name, source, "video/mp4")})
        job_id = job.get("job_id")
        require(isinstance(job_id, str) and re.fullmatch(r"[A-Za-z0-9_-]+", job_id) is not None, "Invalid uploaded job ID")
        self.report["job_id"] = job_id
        self.report["upload"] = job
        require(job.get("status") == "UPLOADED", "Uploaded job has an unexpected status")
        require(job.get("size_bytes") == video.stat().st_size, "Upload size does not match source")
        require(self.job_ids() == before | {job_id}, "Uploaded job not visible in jobs list")
        require(self.json("GET", f"/api/jobs/{job_id}")["job_id"] == job_id, "Uploaded manifest unavailable")
        self.passed("representative video upload", job_id=job_id, size_bytes=job["size_bytes"])
        self.video_range(job_id, "original")
        print(f"Job retained for review: {job_id}", flush=True)
        return job_id

    def infer(self, job_id: str, timeout: float, poll_seconds: float) -> None:
        manifest = self.json("POST", f"/api/jobs/{job_id}/run", 202)
        require(manifest.get("status") in ACTIVE_STATUSES | {"COMPLETED"}, "Analysis did not start")
        self.passed("start independent analysis")
        deadline = time.monotonic() + timeout
        observed: list[dict[str, Any]] = []
        last_status: str | None = None
        transient_errors = 0
        while True:
            status = manifest.get("status")
            progress = manifest.get("progress")
            require(status in ACTIVE_STATUSES | {"COMPLETED", "FAILED"}, f"Unexpected job status: {status}")
            require(isinstance(progress, (int, float)) and 0 <= progress <= 100, "Invalid job progress")
            if status != last_status:
                observed.append({"status": status, "progress": progress, "at": utc_now()})
                self.report["observed_statuses"] = observed
                print(f"Analysis {status} ({progress}%)", flush=True)
                last_status = status
            self.report["last_manifest"] = manifest
            require(status != "FAILED", f"Worker failed: {manifest.get('error') or manifest.get('message')}")
            if status == "COMPLETED":
                require(progress == 100, "Completed job progress is not 100")
                break
            require(time.monotonic() < deadline, f"Analysis exceeded {timeout:g} seconds")
            time.sleep(min(poll_seconds, max(0, deadline - time.monotonic())))
            try:
                response = self.client.get(f"/api/jobs/{job_id}")
                if response.status_code in {500, 502, 503, 504}:
                    transient_errors += 1
                    require(time.monotonic() < deadline, "Polling deadline exceeded during a server error")
                    continue
                require(response.status_code == 200, f"Job polling returned {response.status_code}")
                manifest = response.json()
            except httpx.RequestError:
                transient_errors += 1
                require(time.monotonic() < deadline, "Polling deadline exceeded during a network error")
        self.passed("analysis completed", observed_statuses=observed, transient_poll_errors=transient_errors)

        result = self.json("GET", f"/api/jobs/{job_id}/results")
        require(isinstance(result, dict), "Canonical result is not an object")
        require({"schema_version", "source", "ground_truth_used", "summary", "clusters"} <= result.keys(), "Missing canonical result fields")
        require(result["ground_truth_used"] is False, "Product inference unexpectedly uses ground truth")
        require(isinstance(result["summary"], dict) and SUMMARY_FIELDS <= result["summary"].keys(), "Missing canonical summary fields")
        require(isinstance(result["clusters"], list), "Canonical clusters are not a list")
        require(all(cluster.get("status") in EVIDENCE_STATUSES for cluster in result["clusters"]), "Unexpected evidence state")
        summary = self.json("GET", f"/api/jobs/{job_id}/summary")
        require(summary == {key: result[key] for key in ("schema_version", "source", "ground_truth_used", "summary")}, "Summary differs from canonical result")
        self.report["canonical_result"] = result
        self.passed("canonical results and summary", summary=result["summary"])

        require(bool(result["clusters"]), "Representative video has no clusters; cannot test evidence")
        cluster = next((item for item in result["clusters"] if item.get("observations")), result["clusters"][0])
        cluster_id = cluster["cluster_id"]
        evidence = self.json("GET", f"/api/jobs/{job_id}/clusters/{cluster_id}")
        require(evidence == cluster, "Cluster endpoint differs from canonical evidence")
        self.passed("cluster evidence", cluster_id=cluster_id, evidence_status=cluster["status"])
        crops = [observation["filename"] for observation in cluster.get("observations", [])]
        require(bool(crops), "Representative video has no retained crops; cannot test crop delivery")
        for filename in dict.fromkeys(crops[:3]):
            response = self.response("GET", f"/api/jobs/{job_id}/crops/{quote(filename, safe='')}")
            require(response.headers.get("content-type", "").startswith("image/"), "Crop response is not an image")
            require(response.content.startswith(b"\xff\xd8"), "Crop is not a readable JPEG payload")
        self.passed("evidence crop images", count=len(set(crops[:3])))

        videos = self.json("GET", f"/api/jobs/{job_id}/videos")
        for kind in ("original", "presentation", "analyzed"):
            require(videos.get(kind) == f"/api/jobs/{job_id}/video/{kind}", f"Invalid {kind} video URL")
            self.video_range(job_id, kind)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="AutoVue origin serving both React and FastAPI")
    parser.add_argument("--video", type=Path, help="Small representative MP4 to upload and retain")
    parser.add_argument("--inference", action="store_true", help="Run GPU inference and validate results, crops and processed video")
    parser.add_argument("--timeout", type=float, default=7200, help="Inference polling deadline in seconds (default: 7200, minimum: 3600)")
    parser.add_argument("--poll-seconds", type=float, default=3, help="Interval between progress polls")
    parser.add_argument("--request-timeout", type=float, default=300, help="Individual HTTP request timeout")
    parser.add_argument("--report", type=Path, help="Write JSON evidence report, including failures")
    args = parser.parse_args(argv)
    parsed = urlsplit(args.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error("--url must be an HTTP(S) base URL without credentials, query or fragment")
    if args.inference and args.video is None:
        parser.error("--inference requires --video")
    if args.timeout < 3600 or args.poll_seconds <= 0 or args.request_timeout <= 0:
        parser.error("--timeout must be at least 3600, and polling/request timeouts must be positive")
    if args.video is not None and (not args.video.is_file() or args.video.suffix.lower() != ".mp4"):
        parser.error("--video must be an existing MP4 file")
    username = os.environ.get("AUTOVUE_AUTH_USERNAME", "")
    password = os.environ.get("AUTOVUE_AUTH_PASSWORD", "")
    if bool(username) != bool(password) or ":" in username:
        parser.error("Set both AUTOVUE_AUTH_USERNAME and AUTOVUE_AUTH_PASSWORD with a valid username")
    authenticated = bool(username and password)
    base_url = args.url.rstrip("/")
    report: dict[str, Any] = {
        "base_url": base_url, "started_at": utc_now(), "authenticated": authenticated,
        "inference_requested": args.inference, "checks": [], "passed": False,
    }
    code = 0
    try:
        with httpx.Client(
            base_url=base_url,
            auth=(username, password) if authenticated else None,
            timeout=httpx.Timeout(args.request_timeout, connect=60),
            follow_redirects=False,
        ) as client:
            smoke = Smoke(client, report)
            smoke.initial_checks(authenticated)
            if args.video is not None:
                job_id = smoke.upload(args.video)
                if args.inference:
                    smoke.infer(job_id, args.timeout, args.poll_seconds)
            report["passed"] = True
            print("Smoke checks passed." + (" Public inference verified." if args.inference and parsed.scheme == "https" else ""), flush=True)
    except (SmokeFailure, httpx.HTTPError, ValueError, KeyError, TypeError, OSError) as exc:
        code = 1
        report["error"] = str(exc)
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        code = 130
        report["error"] = "Interrupted; uploaded job retained for review."
        print(report["error"], file=sys.stderr, flush=True)
    finally:
        report["finished_at"] = utc_now()
        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(f"Report: {args.report}", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
