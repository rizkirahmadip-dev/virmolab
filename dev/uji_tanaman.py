"""Uji fitur F1: Senyawa dari tanaman obat (luring & daring).

Jalankan luring:
  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_tanaman.py

Jalankan daring (SPARQL Wikidata & LOTUS langsung):
  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_tanaman.py --daring
"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from virmolab.core import pustaka
from virmolab.core import tanaman


def uji_resolusi_nama_lokal():
    print("[1] Menguji resolusi nama lokal 'sambiloto' & 'kunyit'...", end=" ")
    hasil_sambiloto = tanaman.cari_takson("sambiloto")
    assert hasil_sambiloto, "Gagal menemukan sambiloto"
    s = hasil_sambiloto[0]
    assert s["qid"] == "Q1551608", f"QID sambiloto salah: {s['qid']}"
    assert "Andrographis paniculata" in s["nama_ilmiah"]

    hasil_kunyit = tanaman.cari_takson("kunyit")
    assert hasil_kunyit, "Gagal menemukan kunyit"
    k = hasil_kunyit[0]
    assert k["qid"] == "Q42562", f"QID kunyit salah: {k['qid']}"
    assert "Curcuma longa" in k["nama_ilmiah"]
    print("OK")


def uji_lotus_luring():
    print("[2] Menguji data LOTUS luring (Andrographis & Curcuma)...", end=" ")
    p_androg = Path("dev/data/lotus_andrographis.json")
    p_curc = Path("dev/data/lotus_curcuma.json")
    assert p_androg.exists(), f"Berkas {p_androg} tidak ditemukan"
    assert p_curc.exists(), f"Berkas {p_curc} tidak ditemukan"

    data_androg = json.loads(p_androg.read_text(encoding="utf-8"))
    daftar_androg = tanaman.proses_hasil_lotus(data_androg)
    assert len(daftar_androg) > 0, "Daftar Andrographis kosong"

    # Cari andrografolida: InChIKey BOJKULTULYSRAS-OTESTREVSA-N
    inchikey_androg = "BOJKULTULYSRAS-OTESTREVSA-N"
    cocok_androg = [x for x in daftar_androg if x.get("inchikey") == inchikey_androg]
    assert cocok_androg, f"Andrografolida ({inchikey_androg}) tidak ditemukan di LOTUS Andrographis"
    senyawa_a = cocok_androg[0]
    # Stereo tidak hilang
    assert "@" in senyawa_a.get("smiles", ""), f"Stereo hilang dari andrografolida: {senyawa_a.get('smiles')}"

    # Standarisasi
    std_androg = tanaman.standarisasi(daftar_androg[:10])
    assert len(std_androg) == 10
    assert not std_androg[0].get("galat"), f"Galat standarisasi: {std_androg[0]}"
    assert std_androg[0].get("mw", 0) > 0

    # Uji Curcuma longa: InChIKey kurkumin VFLDPWHFBUODDF-FCXRPNKRSA-N
    data_curc = json.loads(p_curc.read_text(encoding="utf-8"))
    daftar_curc = tanaman.proses_hasil_lotus(data_curc)
    inchikey_kurk = "VFLDPWHFBUODDF-FCXRPNKRSA-N"
    cocok_kurk = [x for x in daftar_curc if x.get("inchikey") == inchikey_kurk]
    assert cocok_kurk, f"Kurkumin ({inchikey_kurk}) tidak ditemukan di LOTUS Curcuma"
    senyawa_k = cocok_kurk[0]
    assert senyawa_k.get("inchikey") == inchikey_kurk
    print("OK")


def uji_penggabungan_duplikat():
    print("[3] Menguji penggabungan duplikat 14-huruf InChIKey...", end=" ")
    lotus = [
        {
            "inchikey": "BOJKULTULYSRAS-OTESTREVSA-N",
            "nama": "Andrographolide",
            "smiles": "C[C@@]12CCC[C@](C)(C1CC[C@@]2([H])C3=CC(=O)OC3)O",
            "rujukan": ["10.1016/j.jep.2014.05.023"],
            "tahun": [2014],
        }
    ]
    coconut = [
        {
            "inchikey": "BOJKULTULYSRAS-OTESTREVSA-N",
            "nama": "CNP0123456",
            "smiles": "C[C@@]12CCC[C@](C)(C1CC[C@@]2([H])C3=CC(=O)OC3)O",
            "rujukan": ["COCONUT"],
            "tahun": [],
        }
    ]
    gabung = tanaman.gabung_senyawa(lotus, coconut)
    assert len(gabung) == 1, f"Harusnya 1 senyawa tergabung, dapat {len(gabung)}"
    g = gabung[0]
    assert g["asal"] == "keduanya", f"Asal harusnya 'keduanya', dapat: {g['asal']}"
    assert len(g["rujukan"]) == 2, f"Rujukan harusnya memuat LOTUS dan COCONUT: {g['rujukan']}"
    print("OK")


def uji_migrasi_sqlite_organisme():
    print("[4] Menguji migrasi skema SQLite COCONUT (kolom organisme)...", end=" ")
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "coconut.db"
        # Buat database lama tanpa kolom organisme
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE senyawa (
                id TEXT PRIMARY KEY,
                nama TEXT,
                smiles TEXT,
                inchikey TEXT,
                mw REAL,
                logp REAL,
                hbd INTEGER,
                hba INTEGER,
                rotb INTEGER,
                sumber TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Jalankan migrasi
        dimigrasi = pustaka.migrasi_coconut(db_path)
        assert dimigrasi, "Harusnya mengembalikan True saat bermigrasi"

        # Periksa kolom organisme ada
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("PRAGMA table_info(senyawa)")
        kolom = [r[1] for r in cur.fetchall()]
        conn.close()
        assert "organisme" in kolom, f"Kolom organisme tidak ada setelah migrasi: {kolom}"
    print("OK")


def uji_rincian_artikel():
    print("[4b] Menguji penggabungan rincian artikel (graf ilmiah Wikidata)...")
    d = [{"artikel": ["Q1", "Q2", "Q3"], "rujukan": [], "tahun": None}]
    tanaman.gabung_rincian(d, {"Q1": {"doi": "10.1/a", "tahun": 2004}, "Q2": {"doi": "10.1/a", "tahun": 2011},
                               "Q3": {}})
    assert d[0]["rujukan"] == ["10.1/a", "Wikidata Q3"], d[0]["rujukan"]
    assert d[0]["tahun"] == 2011, d[0]["tahun"]
    b = [{"senyawa": {"value": "http://www.wikidata.org/entity/Q9"}, "smiles": {"value": "CCO"},
          "artikels": {"value": "http://www.wikidata.org/entity/Q1|http://www.wikidata.org/entity/Q2"}}]
    assert tanaman.proses_hasil_lotus(b)[0]["artikel"] == ["Q1", "Q2"]
    print("    OK: DOI tanpa duplikat, rujukan tanpa DOI jadi QID, tahun terbaru, artikel terurai.")


def uji_daring():
    print("[5] Menguji pengambilan daring (Wikidata & LOTUS)...")
    try:
        taks = tanaman.cari_takson("Andrographis paniculata")
        assert taks, "Takson tidak ditemukan via daring"
        qid = taks[0]["qid"]
        print(f"    Takson ditemukan: {taks[0]['nama_ilmiah']} ({qid})")
        daftar, jejak = tanaman.senyawa_takson(qid, batas=20)
        assert len(daftar) > 0, "Gagal mengambil senyawa takson daring"
        print(f"    Berhasil mengambil {len(daftar)} senyawa via LOTUS SPARQL (Jejak: {jejak.sumber})")
        print("OK (Daring)")
    except Exception as e:
        print(f"    GAGAL daring: {e}")
        raise


def main():
    print("=== Uji Fitur Tanaman VirmoLab ===")
    uji_resolusi_nama_lokal()
    uji_lotus_luring()
    uji_penggabungan_duplikat()
    uji_migrasi_sqlite_organisme()
    uji_rincian_artikel()

    if "--daring" in sys.argv:
        uji_daring()
    else:
        print("[5] Daring: dilewati (jalankan dengan --daring bila ingin uji langsung ke Wikidata)")

    print("\nSemua uji luring LULUS.")


if __name__ == "__main__":
    main()
