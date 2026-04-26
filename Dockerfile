FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM --platform=linux/amd64 python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LD_LIBRARY_PATH=/opt/minizinc/lib

WORKDIR /app

ARG MINIZINC_VERSION=2.6.1
RUN apt-get update \
    && apt-get install -y --no-install-recommends wget ca-certificates \
    && wget -qO /tmp/minizinc.tgz \
       "https://github.com/MiniZinc/MiniZincIDE/releases/download/${MINIZINC_VERSION}/MiniZincIDE-${MINIZINC_VERSION}-bundle-linux-x86_64.tgz" \
    && mkdir -p /opt/minizinc \
    && tar -xzf /tmp/minizinc.tgz -C /opt/minizinc --strip-components=1 \
    && ln -s /opt/minizinc/bin/minizinc /usr/local/bin/minizinc \
    && rm /tmp/minizinc.tgz \
    && apt-get purge -y wget \
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
