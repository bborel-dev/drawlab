FROM node:24-slim AS site
WORKDIR /site
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /drawlab
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
COPY --from=site /site/dist site/
ENV FRONTEND_DIR=/drawlab/site \
    MOCK_AGENTS=false \
    PYTHONUNBUFFERED=1
WORKDIR /drawlab/backend
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
