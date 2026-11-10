import base64
import io
import os
import stat
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "release-domino"
TARGET_SETUP = ROOT / "setup_release_domino_p2.py"

EXCLUDE_DIRS = {
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".git",
    "demo_shop_repo",
    "demo_shop_repo_origin.git",
}

EXCLUDE_EXTS = {".pyc", ".pyo"}


def should_exclude(rel_path: Path) -> bool:
    for part in rel_path.parts:
        if part in EXCLUDE_DIRS:
            return True
    if rel_path.suffix in EXCLUDE_EXTS:
        return True
    return False


def create_archive() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9) as tar:
        for root, dirs, files in os.walk(SOURCE_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in sorted(files):
                file_path = Path(root) / file
                rel = file_path.relative_to(SOURCE_DIR)
                if should_exclude(rel):
                    continue
                tar.add(str(file_path), arcname=rel.as_posix())
    return buf.getvalue()


def repack():
    print(f"Packing {SOURCE_DIR}...")
    archive_bytes = create_archive()
    b64_str = base64.b64encode(archive_bytes).decode("ascii")
    print(f"Archive compressed size: {len(archive_bytes)} bytes (base64: {len(b64_str)} bytes)")

    lines = TARGET_SETUP.read_text(encoding="utf-8").splitlines()
    
    # Locate ARCHIVE_B64 = "..."
    start_idx = None
    for i, line in enumerate(lines):
        if line.startswith("ARCHIVE_B64 = "):
            start_idx = i
            break
            
    if start_idx is None:
        raise ValueError("ARCHIVE_B64 line not found in setup script")

    # Replace the ARCHIVE_B64 line
    lines[start_idx] = f'ARCHIVE_B64 = "{b64_str}"'
    
    TARGET_SETUP.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Updated {TARGET_SETUP} successfully.")


if __name__ == "__main__":
    repack()
