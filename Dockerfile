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
#   Gecode     commit eebbc1bfaef1decd3ab6a3c583c7b55f5fe29600  (release/6.3.0 tip)
#   MiniZinc   tag    2.6.1
#   Python deps  requirements.lock (pip-compile --generate-hashes pyproject.toml)
#   debian:bookworm-slim      sha256:f9c6a2fd2ddbc23e336b6257a5245e31f996953ef06cd13a59fa0a1df2d5c252
#   python:3.11-slim-bookworm sha256:ee710afcfb733f4a750d9be683cf054b5cd247b6c5f5237a6849ea568b90ab15
#   node:22-bookworm-slim     sha256:d415caac2f1f77b98caaf9415c5f807e14bc8d7bdea62561ea2fef4fbd08a73c
#
# To regenerate lock files after changing pyproject.toml:
#   docker run --rm -v $(pwd):/app -w /app \
#     python:3.11-slim-bookworm@sha256:ee710afcfb733f4a750d9be683cf054b5cd247b6c5f5237a6849ea568b90ab15 \
#     sh -c "pip install pip-tools && \
#            pip-compile pyproject.toml --output-file requirements.lock --generate-hashes && \
#            pip-compile --extra notebook pyproject.toml --output-file requirements-notebook.lock --generate-hashes"
# ─────────────────────────────────────────────────────────────────────────────


# ── Stage 1: build Gecode 6.3.0 from source ──────────────────────────────────
FROM debian:bookworm-slim@sha256:f9c6a2fd2ddbc23e336b6257a5245e31f996953ef06cd13a59fa0a1df2d5c252 AS gecode-builder

# No libmpfr-dev: plate-design.mzn uses `float` only as parameter data, never as
# a solver decision variable. Building without MPFR keeps libgecodefloat.a free
# of external MPFR symbols, which avoids a linker bug in libminizinc 2.6.1 where
# FindGecode.cmake never propagates MPFR into Gecode::Float's INTERFACE_LINK_LIBRARIES.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential cmake git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Fetch exact commit rather than branch tip — branch can be force-pushed;
# commit SHA is immutable. GitHub supports fetching arbitrary SHAs.
RUN git init /src/gecode && \
    git -C /src/gecode fetch --depth 1 \
        https://github.com/Gecode/gecode.git \
        eebbc1bfaef1decd3ab6a3c583c7b55f5fe29600 && \
    git -C /src/gecode checkout FETCH_HEAD

RUN cmake -S /src/gecode -B /build/gecode \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/opt/gecode \
        -DENABLE_GIST=OFF \
        -DENABLE_CPPROFILER=OFF
RUN cmake --build /build/gecode --parallel "$(nproc)"
RUN cmake --install /build/gecode


# ── Stage 2: build MiniZinc 2.6.1 from source ────────────────────────────────
FROM debian:bookworm-slim@sha256:f9c6a2fd2ddbc23e336b6257a5245e31f996953ef06cd13a59fa0a1df2d5c252 AS minizinc-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential cmake git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --branch 2.6.1 --depth 1 \
    https://github.com/MiniZinc/libminizinc.git /src/libminizinc

# utils.hh uses std::unique_ptr but omits #include <memory> — GCC 12 (Bookworm)
# does not pull it in transitively, causing a compile error in every translation
# unit that includes utils.hh (including the CPLEX plugin wrapper).
RUN sed -i 's|#include <vector>|#include <memory>\n#include <vector>|' \
    /src/libminizinc/include/minizinc/utils.hh

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
FROM node:22-bookworm-slim@sha256:d415caac2f1f77b98caaf9415c5f807e14bc8d7bdea62561ea2fef4fbd08a73c AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ── Stage 4: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm@sha256:ee710afcfb733f4a750d9be683cf054b5cd247b6c5f5237a6849ea568b90ab15 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/minizinc/bin:/opt/gecode/bin:$PATH"

WORKDIR /app

# Copy solver stack — native ARM64, no GUI deps, no apt solver packages needed
COPY --from=gecode-builder  /opt/gecode    /opt/gecode
COPY --from=minizinc-builder /opt/minizinc  /opt/minizinc

# Register Gecode as a MiniZinc solver.
# fzn-gecode is built by Gecode itself (not libminizinc), so libminizinc's cmake
# never installs a solver config for it. We create the .msc descriptor manually.
# "executable": "fzn-gecode" is found via PATH (/opt/gecode/bin).
RUN mkdir -p /opt/minizinc/share/minizinc/solvers && \
    printf '{\n  "id": "org.gecode.gecode",\n  "name": "Gecode",\n  "description": "Gecode Constraint Solving Toolkit",\n  "version": "6.3.0",\n  "mznlib": "/opt/gecode/share/minizinc/gecode",\n  "executable": "fzn-gecode",\n  "tags": ["cp","int","float","set","default"],\n  "stdFlags": ["-a","-n","-f","-p","-s","-r","-v","-t"],\n  "supportsMzn": false,\n  "supportsFzn": true,\n  "needsSolns2Out": true,\n  "needsMznExecutable": false,\n  "needsStdlibDir": false,\n  "isGUIApplication": false\n}\n' \
    > /opt/minizinc/share/minizinc/solvers/gecode.msc && \
    printf '%% sliding_among stub -- gecode.mzn includes this file but plate-design.mzn\n%% never calls among_seq, so these native predicate declarations are never invoked.\npredicate sliding_among(int: mn, int: mx, int: l, array[int] of var int: x, set of int: S);\npredicate sliding_among(int: mn, int: mx, int: l, array[int] of var bool: x, bool: b);\n' \
    > /opt/gecode/share/minizinc/gecode/sliding_among.mzn

COPY pyproject.toml README.md LICENSE.md requirements.lock ./
COPY src ./src
RUN python -m pip install --upgrade pip \
    && python -m pip install --require-hashes -r requirements.lock \
    && python -m pip install --no-deps .

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

COPY requirements-notebook.lock ./
RUN python -m pip install --require-hashes -r requirements-notebook.lock \
    && python -m pip install --no-deps ".[notebook]"
COPY notebooks ./notebooks

EXPOSE 8888
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", \
     "--notebook-dir=/app", "--ServerApp.token=", "--ServerApp.password="]
