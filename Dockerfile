FROM python:3.11-slim

WORKDIR /app

# makino-ai-companion ディレクトリからコピー
COPY makino-ai-companion/ .

# 軽量版dependencies（sentence-transformers/PyTorch除外）
RUN pip install --no-cache-dir -r requirements-deploy.txt

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
