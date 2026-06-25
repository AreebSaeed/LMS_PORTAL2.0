"""Copy static assets to public/ for Vercel CDN serving."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
PUBLIC_STATIC = ROOT / "public" / "static"


def main():
    PUBLIC_STATIC.parent.mkdir(parents=True, exist_ok=True)
    if PUBLIC_STATIC.exists():
        shutil.rmtree(PUBLIC_STATIC)
    if STATIC.is_dir():
        shutil.copytree(STATIC, PUBLIC_STATIC)
        print(f"Copied {STATIC} -> {PUBLIC_STATIC}")
    else:
        print("No static/ directory found; skipping.")


if __name__ == "__main__":
    main()
