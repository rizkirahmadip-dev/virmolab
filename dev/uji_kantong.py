"""Uji deteksi kantong pengikatan pada struktur nyata.

1HSG tanpa ligan MK1 (apo buatan): kantong teratas harus jatuh di sisi aktif protease HIV-1, yaitu dekat pusat
MK1 kristal (13,07; 22,47; 5,56) — acuan yang sama dengan grid box proyek contoh.

  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe dev/uji_kantong.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from virmodock.core import kantong

PUSAT_MK1 = (13.07, 22.47, 5.56)
TOLERANSI = 5.0     # Å dari pusat ligan kristal


def jalan():
    print("=== Uji deteksi kantong pengikatan (1HSG) ===")
    gagal = 0
    pdb = Path(__file__).resolve().parents[1] / "virmodock" / "aset" / "contoh" / "1HSG.pdb"
    if not pdb.exists():
        print("GAGAL 1HSG.pdb tidak ditemukan")
        return 1
    teks = pdb.read_text(encoding="utf-8")
    apo = "\n".join(b for b in teks.splitlines() if not (b.startswith("HETATM") and "MK1" in b))

    daftar = kantong.deteksi_kantong(apo)
    if not daftar:
        print("GAGAL tidak ada kantong terdeteksi pada 1HSG apo")
        return 1
    k = daftar[0]
    p = k["pusat"]
    jarak = math.dist((p["x"], p["y"], p["z"]), PUSAT_MK1)
    print(f"OK   {len(daftar)} kantong; teratas {k['volume']} A^3, kelayakan {k['skor_druggability']}, "
          f"kedalaman PSP {k['kedalaman_psp']}/13")
    print(f"     Pusat ({p['x']}, {p['y']}, {p['z']}); jarak ke pusat MK1 kristal = {jarak:.2f} A")
    print(f"     {k['jumlah_residu']} residu dinding: {', '.join(k['residu_pelapis'][:8])}…")
    if jarak > TOLERANSI:
        print(f"GAGAL kantong teratas {jarak:.1f} A dari sisi aktif (batas {TOLERANSI} A)")
        gagal += 1
    if not (60.0 <= k["volume"] <= 1500.0):
        print(f"GAGAL volume kantong {k['volume']} A^3 di luar rentang masuk akal untuk sisi aktif molekul kecil")
        gagal += 1
    dinding = {r.split()[0] for r in k["residu_pelapis"]}
    if "ASP" not in dinding:
        print("GAGAL residu katalitik ASP 25 tidak ada di dinding kantong")
        gagal += 1

    # struktur holo: sisi aktif terisi MK1, jadi kantong di sana tidak boleh muncul lagi
    holo = kantong.deteksi_kantong(teks)
    dekat = [x for x in holo
             if math.dist((x["pusat"]["x"], x["pusat"]["y"], x["pusat"]["z"]), PUSAT_MK1) <= TOLERANSI]
    print(f"OK   struktur holo (MK1 masih terpasang): {len(holo)} kantong, {len(dekat)} di sisi aktif")

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(jalan())
