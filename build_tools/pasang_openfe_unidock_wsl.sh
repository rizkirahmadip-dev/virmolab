#!/bin/bash
# Pasang OpenFE (RBFE) dan Uni-Dock (docking GPU) di WSL, bukan di dalam installer VirmoLab.
# Keduanya Linux saja: OpenFE hanya mendukung POSIX, Uni-Dock hanya CUDA Linux.
# OpenFE: MIT. Uni-Dock: Apache-2.0 (sejak 10 Maret 2025). Paket dari conda-forge lewat micromamba,
# masing-masing di lingkungan terpisah supaya versi OpenMM/CUDA keduanya tidak saling mengunci.
set -euo pipefail
ALAT="$HOME/virmolab-alat"
export MAMBA_ROOT_PREFIX="$ALAT/mamba"
MM="$ALAT/micromamba"
mkdir -p "$ALAT"
if [[ ! -x "$MM" ]]; then
  echo "UNDUH_MICROMAMBA"
  curl -L --retry 3 --fail -o "$ALAT/micromamba.tar.bz2" https://micro.mamba.pm/api/micromamba/linux-64/latest
  tar -xjf "$ALAT/micromamba.tar.bz2" -C "$ALAT" bin/micromamba
  mv "$ALAT/bin/micromamba" "$MM"
  rmdir "$ALAT/bin" 2>/dev/null || true
  rm -f "$ALAT/micromamba.tar.bz2"
fi
"$MM" --version
# Driver Windows memberi CUDA ke WSL lewat /usr/lib/wsl/lib; paket GPU conda-forge dipilih bila
# paket virtual __cuda terdeteksi. Ditetapkan eksplisit supaya pemilihan tidak bergantung deteksi.
export CONDA_OVERRIDE_CUDA="${CONDA_OVERRIDE_CUDA:-12.6}"
# Koneksi lambat: unduhan conda-forge sering putus di tengah. Paket yang sudah selesai tersimpan di
# $MAMBA_ROOT_PREFIX/pkgs, jadi percobaan ulang hanya mengambil sisanya.
export MAMBA_REMOTE_MAX_RETRIES=10 MAMBA_REMOTE_BACKOFF_FACTOR=3
export MAMBA_REMOTE_CONNECT_TIMEOUT_SECS=60 MAMBA_REMOTE_READ_TIMEOUT_SECS=600
buat_env() {   # buat_env <folder> <paket...>; ulangi sampai 4 kali bila unduhan putus
  local tujuan="$1"; shift
  for coba in 1 2 3 4; do
    if "$MM" create -y -p "$tujuan" -c conda-forge "$@"; then return 0; fi
    echo "ULANG_UNDUH $coba"; rm -rf "$tujuan"; sleep 20
  done
  return 1
}
if [[ ! -x "$ALAT/openfe/bin/openfe" ]]; then
  echo "UNDUH_OPENFE"
  buat_env "$ALAT/openfe" openfe "python=3.12" "cuda-version=12"
fi
if [[ ! -x "$ALAT/unidock/bin/unidock" ]]; then
  echo "UNDUH_UNIDOCK"
  buat_env "$ALAT/unidock" unidock "cuda-version=12"
fi
echo "VERSI_OPENFE"
"$ALAT/openfe/bin/openfe" --version || true
"$ALAT/openfe/bin/python" -c "import openmm; print('OpenMM', openmm.__version__); \
from openmm import Platform; print('Platform:', [Platform.getPlatform(i).getName() for i in range(Platform.getNumPlatforms())])"
echo "VERSI_UNIDOCK"
"$ALAT/unidock/bin/unidock" --version || "$ALAT/unidock/bin/unidock" --help | head -n 5 || true
# Catatan versi yang benar-benar terpasang, untuk jejak di laporan metode.
"$MM" list -p "$ALAT/openfe" --json > "$ALAT/openfe-paket.json" || true
"$MM" list -p "$ALAT/unidock" --json > "$ALAT/unidock-paket.json" || true
echo PASANG_SELESAI
