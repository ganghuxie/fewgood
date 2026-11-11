import subprocess
from pathlib import Path


def test_merge_cases():
    subprocess.run(['node', 'tests/test_p1_merge.mjs'], cwd=Path(__file__).resolve().parents[1], check=True)
