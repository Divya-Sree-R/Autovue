#!/usr/bin/env python3
"""Measure the unchanged 500 MiB MP4 boundary against an authorized demo URL.

No analysis is started. Uses valid six-second footage padded with an ISO BMFF
free box, so request size grows without extending inference/video duration.
Credentials come from AUTOVUE_AUTH_USERNAME and AUTOVUE_AUTH_PASSWORD.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import time

import httpx

LIMIT = 500 * 1024 * 1024


def padded_mp4(source: Path, destination: Path, size: int):
    padding = size - source.stat().st_size
    if padding < 8 or padding >= 2 ** 32:
        raise ValueError('The small source MP4 must leave room for a valid free box.')
    with source.open('rb') as original, destination.open('xb') as output:
        shutil.copyfileobj(original, output)
        output.write(struct.pack('>I4s', padding, b'free'))
        output.truncate(size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=1800)
    parser.add_argument('--size-mib', type=int, default=500,
                        help='Accepted file size to measure (2-500 MiB; policy remains 500 MiB)')
    parser.add_argument('--include-oversize', action='store_true',
                        help='Also send 500 MiB + 1 byte and require HTTP 413 with no orphan job')
    args = parser.parse_args()
    if not 2 <= args.size_mib <= 500:
        parser.error('--size-mib must be between 2 and 500; this does not change the server limit.')
    from urllib.parse import urlsplit
    origin = urlsplit(args.url)
    if origin.scheme not in {'http', 'https'} or not origin.netloc or origin.username or origin.password or origin.query or origin.fragment:
        parser.error('Use a base URL without embedded credentials or query parameters.')
    auth = (os.environ.get('AUTOVUE_AUTH_USERNAME', ''), os.environ.get('AUTOVUE_AUTH_PASSWORD', ''))
    if not all(auth):
        parser.error('Authentication environment variables are required.')
    report = {'url': args.url.rstrip('/'), 'started_at': datetime.now(timezone.utc).isoformat(),
              'file_limit_bytes': LIMIT, 'tested_file_bytes': args.size_mib * 1024 * 1024,
              'passed': False, 'checks': []}
    try:
        with tempfile.TemporaryDirectory(prefix='autovue-upload-boundary-') as directory, \
             httpx.Client(base_url=report['url'], auth=auth,
                          timeout=httpx.Timeout(args.timeout, connect=60)) as client:
            cases = [(args.size_mib * 1024 * 1024, 201)]
            if args.include_oversize:
                cases.append((LIMIT + 1, 413))
            for size, expected in cases:
                before_response = client.get('/api/jobs')
                before_response.raise_for_status()
                before = {job['job_id'] for job in before_response.json()['jobs']}
                payload = Path(directory) / f'boundary-{size}.mp4'
                padded_mp4(args.video, payload, size)
                print(f'Testing {size} bytes; waiting for the real upload response...', flush=True)
                started = time.monotonic()
                with payload.open('rb') as video:
                    response = client.post('/api/jobs', files={'file': (payload.name, video, 'video/mp4')})
                check = {'bytes': size, 'expected_http': expected, 'actual_http': response.status_code,
                         'elapsed_seconds': round(time.monotonic() - started, 3)}
                report['checks'].append(check)
                assert response.status_code == expected, f'Upload of {size} bytes returned {response.status_code}: {response.text[:200]}'
                after_response = client.get('/api/jobs')
                after_response.raise_for_status()
                after = {job['job_id'] for job in after_response.json()['jobs']}
                if expected == 201:
                    job = response.json()
                    assert job['size_bytes'] == size and after == before | {job['job_id']}
                    check['job_id'] = job['job_id']
                    check['status'] = job['status']
                    # Verify actual persisted bytes and range support, not just a manifest.
                    media = client.get(f"/api/jobs/{job['job_id']}/video/original", headers={'Range': f'bytes={size-16}-{size-1}'})
                    assert media.status_code == 206 and len(media.content) == 16
                    check['range_http'] = media.status_code
                else:
                    assert before == after, 'Rejected upload left an orphan job.'
                print(f"PASS {size} bytes -> HTTP {response.status_code} in {check['elapsed_seconds']}s", flush=True)
            report['passed'] = True
    except Exception as exc:
        report['error'] = str(exc)
        print('FAIL ' + str(exc), flush=True)
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
