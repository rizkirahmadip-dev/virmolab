# -*- coding: utf-8 -*-
"""Sinyal Qt yang disambung langsung ke metode berparameter opsional menimpa parameter itu.

clicked, toggled, triggered, pressed, dan released mengirim satu argumen bool. Menyambungkannya
langsung ke metode yang punya parameter dengan nilai bawaan membuat bool itu mengisi parameter
pertama, dan nilai bawaannya tidak pernah terpakai.

Bentuknya diam: tidak ada galat, tidak ada tanda apa pun di log, tombolnya hanya mengerjakan hal
yang salah. Dua di antaranya ditemukan dari laporan pengguna, bukan dari uji:

- dialog_fleksibel "Pilih 6 terdekat" terpanggil dengan n=False, yaitu nol, sehingga tombolnya
  justru mengosongkan seluruh daftar alih-alih mencentang enam residu terdekat.
- pemutar_trajektori "Putar / jeda" terpanggil dengan putar=False, sehingga `not putar` selalu
  benar dan tombolnya selalu menjeda, tidak pernah memutar.

Perbaikannya selalu sama: bungkus dengan lambda tanpa argumen.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/cek_sinyal_qt.py
"""
import ast
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
SINYAL = {"clicked", "toggled", "triggered", "pressed", "released"}


def periksa(akar: Path):
    temuan = []
    for berkas in sorted(akar.rglob("*.py")):
        try:
            pohon = ast.parse(berkas.read_text(encoding="utf-8"))
        except SyntaxError as e:
            temuan.append((berkas, 0, "(tidak dapat diurai)", str(e)))
            continue
        metode = {n.name: (len(n.args.args) - 1, len(n.args.defaults))
                  for n in ast.walk(pohon) if isinstance(n, ast.FunctionDef)}
        for n in ast.walk(pohon):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "connect" and n.args):
                continue
            if not (isinstance(n.func.value, ast.Attribute) and n.func.value.attr in SINYAL):
                continue
            a = n.args[0]
            if not (isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name)
                    and a.value.id == "self" and a.attr in metode):
                continue
            n_pos, n_bawaan = metode[a.attr]
            if n_pos >= 1 and n_bawaan >= 1:
                temuan.append((berkas, n.lineno, f"{n.func.value.attr}.connect(self.{a.attr})",
                               f"{a.attr} menerima {n_pos} parameter dengan {n_bawaan} nilai bawaan; "
                               "bool dari sinyal akan mengisi yang pertama"))
    return temuan


def main():
    temuan = periksa(AKAR / "virmolab")
    for berkas, baris, apa, kenapa in temuan:
        print(f"GAGAL {berkas.relative_to(AKAR)}:{baris}  {apa}\n        {kenapa}\n"
              f"        perbaikan: bungkus dengan lambda tanpa argumen")
    print(("GAGAL " + str(len(temuan))) if temuan else "LULUS 0", flush=True)
    return 1 if temuan else 0


if __name__ == "__main__":
    sys.exit(main())
