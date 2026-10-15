#!/usr/bin/env python3
"""Install a checksum-pinned free Tailscale client in private runtime storage."""
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deploy.local_app import private_directory
from deploy.tailscale_funnel import ARCHIVE_SHA256, DEFAULT_STATE, VERSION


def main():
    if platform.system() != 'Linux' or platform.machine() not in {'x86_64', 'amd64'}:
        raise RuntimeError('This pinned client is for Linux/WSL AMD64 only.')
    private_directory(DEFAULT_STATE)
    bins = DEFAULT_STATE / 'bin'
    private_directory(bins)
    if all((bins / name).is_file() and not (bins / name).is_symlink() for name in ('tailscale', 'tailscaled')):
        found = subprocess.check_output([str(bins / 'tailscale'), 'version'], text=True).splitlines()[0]
        if found == VERSION:
            print(f'Verified client version {VERSION} is already installed in {bins}.')
            return
        raise RuntimeError('An existing different client version is preserved; review it before replacement.')
    if any((bins / name).exists() or (bins / name).is_symlink() for name in ('tailscale', 'tailscaled')):
        raise RuntimeError('An incomplete existing installation is preserved; inspect the private bin directory.')
    url = f'https://pkgs.tailscale.com/stable/tailscale_{VERSION}_amd64.tgz'
    with tempfile.TemporaryDirectory(prefix='install-', dir=DEFAULT_STATE) as directory:
        archive = Path(directory) / 'tailscale.tgz'
        with urlopen(url, timeout=180) as response, archive.open('xb') as destination:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 128 * 1024 * 1024:
                    raise RuntimeError('Unexpectedly large Tailscale archive.')
                destination.write(chunk)
        with archive.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != ARCHIVE_SHA256:
                raise RuntimeError('Tailscale archive checksum did not match; nothing was installed.')
        with tarfile.open(archive, 'r:gz') as source:
            for name in ('tailscale', 'tailscaled'):
                member = source.getmember(f'tailscale_{VERSION}_amd64/{name}')
                if not member.isfile():
                    raise RuntimeError('Unexpected archive contents.')
                descriptor = os.open(bins / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o700)
                with source.extractfile(member) as data, os.fdopen(descriptor, 'wb') as destination:
                    shutil.copyfileobj(data, destination)
    print(f'Installed checksum-verified Tailscale {VERSION} in {bins}; no system service or public exposure.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'AutoVue Tailscale install: {exc}', file=sys.stderr)
        raise SystemExit(1)
