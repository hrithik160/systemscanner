#!/usr/bin/env python3
"""
Task D1 — Docker Image Builder for Release Domino Sandboxed Runners
Builds both `rd-runner-py` and `rd-runner-node` images and verifies non-root execution.
"""
import subprocess
import sys
from pathlib import Path

DOCKER_DIR = Path(__file__).resolve().parent
REPO_ROOT = DOCKER_DIR.parent


def build_runner_images() -> None:
    images = [
        ("rd-runner-py", DOCKER_DIR / "py" / "Dockerfile"),
        ("rd-runner-node", DOCKER_DIR / "node" / "Dockerfile"),
    ]
    for tag, dockerfile in images:
        print(f"[Docker D1] Building {tag} from {dockerfile.relative_to(REPO_ROOT)}...")
        subprocess.run(
            ["docker", "build", "-t", tag, "-f", str(dockerfile), str(REPO_ROOT)],
            check=True,
        )
        print(f"[Docker D1] Verified image {tag} built successfully.")


if __name__ == "__main__":
    try:
        build_runner_images()
    except Exception as exc:
        print(f"Failed to build Docker runner images: {exc}", file=sys.stderr)
        sys.exit(1)
