FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim-bullseye AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends minizinc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE.md ./
COPY src ./src
RUN python -m pip install --upgrade pip \
    && python -m pip install .

COPY backend ./backend
COPY config ./config
COPY data ./data
COPY inputs ./inputs
COPY scripts ./scripts
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

RUN mkdir -p backend/data/jobs outputs/results outputs/logs

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM runtime AS notebook

RUN python -m pip install ".[notebook]"

COPY notebooks ./notebooks

EXPOSE 8888

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", \
     "--notebook-dir=/app", "--ServerApp.token=", "--ServerApp.password="]
