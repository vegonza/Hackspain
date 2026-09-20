#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec docker compose --env-file "$PROJECT_DIR/backend/.env" -f "$PROJECT_DIR/docker-compose.yml" up --build -d "$@"
