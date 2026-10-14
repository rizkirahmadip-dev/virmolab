#!/bin/bash
# Pasang GNINA 1.3.3 dan Boltz 2.2.1 di WSL (bukan di dalam installer VirmoLab).
# GNINA: biner Linux CUDA 12.8, lisensi GPL-2.0 karena menyertakan OpenBabel.
# Boltz: MIT, lingkungan Python 3.12 terpisah (paket PyPI menolak Python 3.14).
set -euo pipefail
ALAT="$HOME/virmolab-alat"
mkdir -p "$ALAT"
if [[ ! -x "$ALAT/gnina" ]]; then
  echo "UNDUH_GNINA"
  curl -L --retry 3 --fail -o "$ALAT/gnina.part" \
    https://github.com/gnina/gnina/releases/download/v1.3.3/gnina.cuda12.8.static
  mv "$ALAT/gnina.part" "$ALAT/gnina"
  chmod +x "$ALAT/gnina"
fi
if [[ ! -x "$HOME/.local/bin/uv" ]]; then
  echo "UNDUH_UV"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
if [[ ! -x "$ALAT/boltz/bin/python" ]]; then
  echo "PYTHON_312"
  uv python install 3.12
  uv venv "$ALAT/boltz" --python 3.12
fi
PY="$ALAT/boltz/bin/python"
if ! "$PY" -c "import torch" >/dev/null 2>&1; then
  echo "UNDUH_TORCH"
  UV_HTTP_TIMEOUT=300 uv pip install --python "$PY" torch --index-url https://download.pytorch.org/whl/cu126
fi
if ! "$PY" -c "import boltz" >/dev/null 2>&1; then
  echo "UNDUH_BOLTZ"
  uv pip install --python "$PY" "boltz==2.2.1"
fi
echo "BANTUAN_GNINA"
CUDA_LIBS=$(find "$ALAT/boltz/lib" -type d -name lib -path "*/nvidia/*" 2>/dev/null | paste -sd: || true)
if [[ -n "${CUDA_LIBS:-}" ]]; then
  export LD_LIBRARY_PATH="${CUDA_LIBS}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
"$ALAT/gnina" --help | head -n 8 || true
echo "BANTUAN_BOLTZ"
"$ALAT/boltz/bin/boltz" predict --help || true
echo PASANG_SELESAI
