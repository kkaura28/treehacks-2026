"""
Upload a surgical video to Supabase Storage.

Usage:
  python upload_video.py path/to/video.mp4
  python upload_video.py path/to/video.mp4 --name custom-name
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from config import get_supabase

BUCKET = "surgical-videos"


def _ensure_bucket(sb):
    """Create the storage bucket if it doesn't exist."""
    try:
        sb.storage.get_bucket(BUCKET)
    except Exception:
        print(f"  Bucket '{BUCKET}' not found — creating it...")
        sb.storage.create_bucket(BUCKET, options={"public": True})
        print(f"  Bucket created.")


def upload(video_path: str, name: str | None = None) -> str:
    sb = get_supabase()
    p = Path(video_path)

    if not p.exists():
        print(f"File not found: {video_path}")
        sys.exit(1)

    _ensure_bucket(sb)

    storage_name = name or p.stem
    storage_path = f"{storage_name}{p.suffix}"
    mime = "video/mp4" if p.suffix == ".mp4" else f"video/{p.suffix.lstrip('.')}"

    print(f"Uploading {p.name} ({p.stat().st_size / 1024 / 1024:.1f} MB) → {BUCKET}/{storage_path}")

    with open(p, "rb") as f:
        sb.storage.from_(BUCKET).upload(
            path=storage_path,
            file=f,
            file_options={"content-type": mime},
        )

    url = sb.storage.from_(BUCKET).get_public_url(storage_path)
    print(f"Done: {url}")
    return url


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python upload_video.py <video_path> [--name <name>]")
        sys.exit(1)

    video = sys.argv[1]
    name = None
    if "--name" in sys.argv:
        idx = sys.argv.index("--name")
        if idx + 1 < len(sys.argv):
            name = sys.argv[idx + 1]

    upload(video, name)

