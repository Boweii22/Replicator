FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
COPY packages packages
COPY services services
RUN pip install --no-cache-dir .
ENV PORT=8080
CMD ["sh", "-c", "uvicorn services.api.main:app --host 0.0.0.0 --port ${PORT}"]

