FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd -m appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Embedding semantic sungguhan (multilingual). Tanpa ini sistem memakai HashingEmbedder (offline, lebih sederhana).
# Build dengan:  docker compose build --build-arg INSTALL_ST=1 backend
ARG INSTALL_ST=0
RUN if [ "$INSTALL_ST" = "1" ]; then pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir sentence-transformers; fi
COPY . .
RUN mkdir -p /app/data/uploads /home/appuser/.cache && chown -R appuser /app /home/appuser
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
