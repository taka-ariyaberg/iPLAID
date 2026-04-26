# ─────────────────────────────────────────────────────────────────────────────
# iPLAID Dockerfile
#
# MiniZinc/Gecode strategy
# ─────────────────────────
# MiniZinc publishes only x86_64 Linux bundles (confirmed to v2.9.6 — no ARM64).
# The IDE bundle carries Qt5/libGL/libsystemd dependencies absent in headless
# containers. Building the solver stack from source gives native ARM64, no GUI.
#
#   Gecode 6.3.0   — branch release/6.3.0 of https://github.com/Gecode/gecode
#                    (never received a release tag; this is the exact version used
#                    by MiniZinc 2.6.1, confirmed via minizinc-vendor submodule)
#   MiniZinc 2.6.1 — https://github.com/MiniZinc/libminizinc tag 2.6.1
#
# FindGecode.cmake in libminizinc searches ${PROJECT_SOURCE_DIR}/vendor/gecode
# first. We build Gecode in Stage 1, then copy it into that vendor path before
# cmake runs in Stage 2 so detection is guaranteed without any cmake flag hacks.
#
# First build takes ~20-40 min (compiling Gecode + MiniZinc from source).
# Each stage is independently cached — only a version change triggers a rebuild
# of that stage and its dependents.
#
# Pinned versions — change deliberately, test after every bump:
#   Gecode     branch release/6.3.0  (commit eebbc1bfaef1decd3ab6a3c583c7b55f5fe29600)
#   MiniZinc   tag    2.6.1
#   Python     3.11   python:3.11-slim-bookworm
#   Node       22     node:22-bookworm-slim
# ─────────────────────────────────────────────────────────────────────────────


# ── Stage 1: build Gecode 6.3.0 from source ──────────────────────────────────
FROM debian:bookworm-slim AS gecode-builder

# libmpfr-dev: Gecode float-constraint support (used in plate-design.mzn)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential cmake git ca-certificates libmpfr-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --branch release/6.3.0 --depth 1 \
    https://github.com/Gecode/gecode.git /src/gecode

RUN cmake -S /src/gecode -B /build/gecode \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/opt/gecode \
        -DENABLE_GIST=OFF \
        -DENABLE_CPPROFILER=OFF
RUN cmake --build /build/gecode --parallel "$(nproc)"
RUN cmake --install /build/gecode


# ── Stage 2: build MiniZinc 2.6.1 from source ────────────────────────────────
FROM debian:bookworm-slim AS minizinc-builder

# libmpfr-dev needed here too: FindGecode.cmake links MPFR into the mzn library
# if Gecode was built with MPFR support (GECODE_HAS_MPFR in config.hpp)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential cmake git ca-certificates libmpfr-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --branch 2.6.1 --depth 1 \
    https://github.com/MiniZinc/libminizinc.git /src/libminizinc

# FindGecode.cmake searches ${PROJECT_SOURCE_DIR}/vendor/gecode first.
# Placing our built Gecode there is the only reliable detection path —
# -DGECODE_HOME and -DGecode_ROOT are not used by libminizinc's FindGecode.cmake.
RUN mkdir -p /src/libminizinc/vendor/gecode
COPY --from=gecode-builder /opt/gecode/. /src/libminizinc/vendor/gecode/

# Split into separate RUN commands so Docker reports which step fails
RUN cmake -S /src/libminizinc -B /build/minizinc \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/opt/minizinc \
        -DBUILD_TESTING=OFF
RUN cmake --build /build/minizinc --parallel "$(nproc)"
RUN cmake --install /build/minizinc


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

# Copy solver stack — native ARM64, no GUI deps, no apt solver packages needed
COPY --from=gecode-builder  /opt/gecode    /opt/gecode
COPY --from=minizinc-builder /opt/minizinc  /opt/minizinc

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
