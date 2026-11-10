#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$DIR/make_demo_repo.py" "${1:-$DIR/demo_shop_repo}"
