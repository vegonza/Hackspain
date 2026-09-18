#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$PROJECT_DIR/500-sombras-de-alberto/alberto_erp.py" "$@"
