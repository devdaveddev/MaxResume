"""Deploy MaxResume to a Hugging Face Space (Docker SDK).

Builds a clean bundle from what is *committed* in git (never local junk such as
node_modules, .venv or uncommitted edits), adds the Space Dockerfile and model
card at the bundle root, creates the Space if needed, and uploads it.
Hugging Face then builds the image and serves it at https://<user>-<space>.hf.space

Usage (from the repository root):
    uv run --with huggingface_hub python deploy/huggingface/deploy.py --space <user>/<space-name>

Authentication: run `uvx --from huggingface_hub hf auth login` once (or set HF_TOKEN).
Optional Space secrets (set in the Space settings): MONGO_URL for persistent storage,
API_KEYS to require an API key.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INCLUDE = ["backend/pyproject.toml", "backend/uv.lock", "backend/app", "frontend", "sample_data"]


def build_bundle(dest: Path, ref: str) -> None:
    """Extract the committed files for INCLUDE at `ref` into dest."""
    archive = dest / "bundle.tar"
    subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", "-o", str(archive), ref, *INCLUDE], check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(dest, filter="data")
    archive.unlink()
    shutil.copy(HERE / "Dockerfile", dest / "Dockerfile")
    shutil.copy(HERE / "SPACE_README.md", dest / "README.md")
    (dest / ".dockerignore").write_text("**/node_modules\n**/.venv\n**/__pycache__\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--space", required=True, help="<user>/<space-name>")
    parser.add_argument("--ref", default="HEAD", help="git ref to deploy (default: HEAD)")
    parser.add_argument("--private", action="store_true", help="create the Space as private")
    parser.add_argument("--dry-run", action="store_true", help="only build the bundle and print its path")
    args = parser.parse_args()

    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", args.ref],
                            capture_output=True, text=True, check=True).stdout.strip()
    tmp = Path(tempfile.mkdtemp(prefix="maxresume-space-"))
    build_bundle(tmp, args.ref)
    print(f"Bundle for {commit} ready at {tmp}")
    if args.dry_run:
        return

    api = HfApi()
    api.create_repo(args.space, repo_type="space", space_sdk="docker", private=args.private, exist_ok=True)
    api.upload_folder(folder_path=str(tmp), repo_id=args.space, repo_type="space",
                      commit_message=f"Deploy {commit}", delete_patterns=["*"])
    user, name = args.space.split("/")
    print(f"Uploaded. Build logs: https://huggingface.co/spaces/{args.space}")
    print(f"App URL (once built): https://{user.lower()}-{name.lower().replace('_', '-')}.hf.space")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
