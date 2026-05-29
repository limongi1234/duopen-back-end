#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Sobe o stack de desenvolvimento local de uma vez:
#   1. Redis (via redislite — sem Docker/sudo)
#   2. Worker Celery
#   3. API FastAPI (uvicorn, em foreground com --reload)
#
# Ctrl+C encerra tudo. Variáveis opcionais: VENV (default .venv), PORT (default 8000).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")/.."

VENV="${VENV:-.venv}"
PY="$VENV/bin/python"
PORT="${PORT:-8000}"

if [ ! -x "$PY" ]; then
  echo "✗ venv não encontrada em '$VENV'."
  echo "  Crie com: python -m venv $VENV && $VENV/bin/pip install -r requirements.txt"
  exit 1
fi

if [ ! -f .env ]; then
  echo "✗ Falta o arquivo .env."
  echo "  Copie de .env.example e preencha ao menos SUPABASE_URL, SUPABASE_KEY, SECRET_KEY."
  exit 1
fi

PIDS=()
cleanup() {
  echo ""
  echo "→ Encerrando worker/redis..."
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  # redislite sobe um redis-server filho que pode sobreviver ao pai:
  pkill -f "redislite" 2>/dev/null || true
  pkill -f "redis-server 127.0.0.1:6379" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Garante o redislite (Redis local sem Docker)
if ! "$PY" -c "import redislite" 2>/dev/null; then
  echo "→ Instalando redislite (Redis local sem Docker)..."
  "$VENV/bin/pip" install -q redislite
fi

# 1) Redis na porta 6379
echo "→ Subindo Redis (redislite) em 127.0.0.1:6379..."
"$PY" - <<'PYEOF' &
from redislite import Redis
import time
Redis(serverconfig={"port": "6379", "bind": "127.0.0.1"})
while True:
    time.sleep(3600)
PYEOF
PIDS+=($!)
sleep 4

# 2) Worker Celery
echo "→ Subindo worker Celery..."
"$VENV/bin/celery" -A app.tasks.celery_app worker --loglevel=info --pool=solo &
PIDS+=($!)

# 3) API (foreground)
echo "→ Subindo API em http://localhost:${PORT}  (Swagger em /docs · Ctrl+C encerra tudo)"
exec "$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port "$PORT" --reload
