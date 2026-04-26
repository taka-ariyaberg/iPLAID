# ─────────────────────────────────────────────────────────────────────────────
# iPLAID Dockerfile
#
# MiniZinc strategy
# -----------------
# MiniZinc publishes only x86_64 Linux binaries (no ARM64, confirmed to v2.9.6).
# Running the IDE bundle under QEMU emulation is fragile and slow; the bundle
# requires Qt5/libGL which are absent in headless containers.
#
# Fix: build the MiniZinc *compiler* from source (libminizinc, no IDE/Qt/GL),
# then use the Gecode solver from the Debian Bookworm arm64 package.
# Both run natively on ARM64, no emulation layer, no GUI dependencies.
#
# Pinned versions — change deliberately and test after any bump:
#   MiniZinc  2.6.1   https://github.com/MiniZinc/libminizinc/releases/tag/2.6.1
#   Gecode    6.3.0   Debian Bookworm: gecode=6.3.0+dfsg1-2 (matches MZN 2.6.1 bundle)
#   Python    3.11    python:3.11-slim-bookworm
#   Node      22      node:22-bookworm-slim
# ─────────────────────────────────────────────────────────────────────────────


# ── Stage 1: compile MiniZinc 2.6.1 from source ──────────────────────────────
FROM debian:bookworm-slim AS minizinc-builder

ARG MINIZINC_VERSION=2.6.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential cmake git ca-certificates libgecode-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --branch ${MINIZINC_VERSION} --depth 1 \
    https://github.com/MiniZinc/libminizinc.git /src/libminizinc

RUN cmake -S /src/libminizinc -B /build/minizinc \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/opt/minizinc \
        -DBUILD_TESTING=OFF \
        -DGECODE_HOME=/usr \
    && cmake --build /build/minizinc --parallel "$(nproc)" \
    && cmake --install /build/minizinc


# ── Stage 2: build React frontend ────────────────────────────────────────────
FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ── Stage 3: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Gecode from apt: arm64-native, headless (fzn-gecode + libgecode.so), no Qt/GL.
# 6.3.0 on Bookworm matches MiniZinc 2.6.1's bundled version — fully compatible.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gecode \
    && rm -rf /var/lib/apt/lists/*

# MiniZinc compiler + stdlib + solver descriptors (compiled above)
COPY --from=minizinc-builder /opt/minizinc /opt/minizinc
ENV PATH="/opt/minizinc/bin:$PATH"

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


# ── Stage 4: notebook variant (extends runtime) ───────────────────────────────
FROM runtime AS notebook

RUN python -m pip install ".[notebook]"
COPY notebooks ./notebooks

EXPOSE 8888
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", \
     "--notebook-dir=/app", "--ServerApp.token=", "--ServerApp.password="]
