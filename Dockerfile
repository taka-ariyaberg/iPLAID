# ─────────────────────────────────────────────────────────────────────────────
# iPLAID Dockerfile
#
# MiniZinc/Gecode strategy
# ─────────────────────────
# MiniZinc publishes only x86_64 Linux bundles (confirmed to v2.9.6 — no ARM64).
# The IDE bundle is a desktop GUI package: it carries Qt5/libGL/libsystemd that
# have no place in a headless server container and cause cascading lib errors.
#
# Fix: build the solver stack from source — native ARM64, zero GUI deps.
#
#   Gecode 6.3.0  — branch release/6.3.0 of https://github.com/Gecode/gecode
#                   (never got a release tag; confirmed as the exact version used
#                   by MiniZinc 2.6.1 via the minizinc-vendor submodule config)
#   MiniZinc 2.6.1 — https://github.com/MiniZinc/libminizinc tag 2.6.1
#                    (needs Gecode ≥6.3 for its find_package check; needs ≥2.6.0
#                    for the `default` keyword used in plate-design.mzn)
#
# First build compiles from source and takes ~20-40 min on Apple Silicon.
# Docker caches each stage independently, so only a version change triggers
# a rebuild of that stage and everything downstream.
#
# Pinned versions — change deliberately, test after every bump:
#   Gecode     branch release/6.3.0  (commit eebbc1bfaef1decd3ab6a3c583c7b55f5fe29600)
#   MiniZinc   tag    2.6.1
#   Python     3.11   python:3.11-slim-bookworm
#   Node       22     node:22-bookworm-slim
# ─────────────────────────────────────────────────────────────────────────────


# ── Stage 1: build Gecode 6.3.0 from source ──────────────────────────────────
FROM debian:bookworm-slim AS gecode-builder

# libmpfr-dev: Gecode float support (used by the plate-design model)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential cmake git ca-certificates libmpfr-dev \
    && rm -rf /var/lib/apt/lists/*

# Gecode 6.3.0 — lives on a branch, no release tag
RUN git clone --branch release/6.3.0 --depth 1 \
    https://github.com/Gecode/gecode.git /src/gecode

RUN cmake -S /src/gecode -B /build/gecode \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/opt/gecode \
        -DENABLE_GIST=OFF \
        -DENABLE_CPPROFILER=OFF \
    && cmake --build /build/gecode --parallel "$(nproc)" \
    && cmake --install /build/gecode


# ── Stage 2: build MiniZinc 2.6.1 from source ────────────────────────────────
FROM debian:bookworm-slim AS minizinc-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential cmake git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pull in the built Gecode so cmake can detect it
COPY --from=gecode-builder /opt/gecode /opt/gecode

RUN git clone --branch 2.6.1 --depth 1 \
    https://github.com/MiniZinc/libminizinc.git /src/libminizinc

RUN cmake -S /src/libminizinc -B /build/minizinc \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/opt/minizinc \
        -DBUILD_TESTING=OFF \
        -DGECODE_HOME=/opt/gecode \
    && cmake --build /build/minizinc --parallel "$(nproc)" \
    && cmake --install /build/minizinc


# ── Stage 3: build React frontend ────────────────────────────────────────────
FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ── Stage 4: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/minizinc/bin:/opt/gecode/bin:$PATH" \
    LD_LIBRARY_PATH="/opt/gecode/lib:/opt/minizinc/lib"

WORKDIR /app

# Solver stack: native ARM64, no Qt, no OpenGL, no emulation
COPY --from=gecode-builder  /opt/gecode   /opt/gecode
COPY --from=minizinc-builder /opt/minizinc /opt/minizinc

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


# ── Stage 5: notebook variant (extends runtime) ───────────────────────────────
FROM runtime AS notebook

RUN python -m pip install ".[notebook]"
COPY notebooks ./notebooks

EXPOSE 8888
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", \
     "--notebook-dir=/app", "--ServerApp.token=", "--ServerApp.password="]
