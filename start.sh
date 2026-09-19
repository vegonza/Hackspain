#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
git -C "$PROJECT_DIR" submodule update --init --recursive -- 500-sombras-de-alberto
if [[ ! -f "$PROJECT_DIR/backend/.env" ]]; then
  echo "Falta backend/.env: copia backend/.env.example y configura las credenciales." >&2
  exit 1
fi
exec docker compose -f "$PROJECT_DIR/docker-compose.dev.yml" up --build --watch "$@"
