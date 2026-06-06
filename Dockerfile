FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Roda como usuário não-root (menor privilégio). Evita o SecurityWarning do
# Celery e não deixa os containers (web e worker) rodando como root.
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

# Serviço web (padrão). Bind na porta que o Railway injeta via $PORT (shell-form
# para a variável expandir); cai em 8000 localmente. O worker Celery reutiliza
# esta mesma imagem, sobrescrevendo o start command no Railway/Compose por:
#   celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
