FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Serviço web (padrão). O worker Celery reutiliza esta mesma imagem,
# sobrescrevendo o start command no Railway/Compose por:
#   celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
