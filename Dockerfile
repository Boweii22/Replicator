FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
COPY apps apps
COPY packages packages
COPY runner runner
COPY services services
RUN pip install --no-cache-dir .
ENV PORT=8080
CMD ["sh", "-c", "uvicorn ${APP_MODULE:-services.api.main:app} --host 0.0.0.0 --port ${PORT}"]
