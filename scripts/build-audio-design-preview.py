#!/usr/bin/env python3
"""Build without production dotenv files; restore and checksum in finally."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
site = root / 'site'
env = {k: v for k, v in os.environ.items() if not k.startswith(('PUBLIC_', 'SUPABASE_', 'POSTHOG_'))}
env['PUBLIC_BASE'] = '/fewgood-audio-podcast-preview'
with tempfile.TemporaryDirectory(prefix='fewgood-build-env-') as directory:
    moved = []
    try:
        for path in site.glob('.env*'):
            if path.is_file() and path.name not in {'.env.example', '.env.sample'}:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                saved = Path(directory) / path.name
                path.rename(saved)
                moved.append((path, saved, digest))
        subprocess.run(['npm', 'run', 'build'], cwd=site, env=env, check=True)
    finally:
        for path, saved, digest in moved:
            saved.rename(path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise RuntimeError('Environment file checksum mismatch')
        print('Environment files restored; checksums verified.')
