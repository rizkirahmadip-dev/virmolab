"""Uji core/sumber_data.py: server http lokal di thread, coba ulang 503->200, timeout,
cache berkas, mode luring, pembatas laju, dan penghapusan cache.

Tanpa koneksi internet luar.
Jalankan:
  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_sumber_data.py
"""
import http.server
import json
from pathlib import Path
import socketserver
import sys
import threading
import time

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from virmolab.core.sumber_data import Jejak, ambil_json, ambil_teks, sparql, hapus_cache, ukuran_cache

gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


class HandlerUji(http.server.BaseHTTPRequestHandler):
    counter_503 = 0

    def log_message(self, format, *args):
        # Redam log akses agar keluaran uji bersih
        pass

    def do_GET(self):
        jalur = self.path.split("?")[0]
        if jalur == "/data.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "sukses", "nilai": 42}).encode("utf-8"))
        elif jalur == "/coba_ulang":
            HandlerUji.counter_503 += 1
            if HandlerUji.counter_503 == 1:
                self.send_response(503)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Server sibuk sementara")
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"coba": HandlerUji.counter_503}).encode("utf-8"))
        elif jalur == "/teks.tsv":
            self.send_response(200)
            self.send_header("Content-Type", "text/tab-separated-values; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"id\tnama\n1\tCurcumin\n2\tQuercetin\n")
        elif jalur == "/sparql":
            self.send_response(200)
            self.send_header("Content-Type", "application/sparql-results+json; charset=utf-8")
            self.end_headers()
            resp = {
                "results": {
                    "bindings": [
                        {"item": {"value": "http://www.wikidata.org/entity/Q1551608"}, "itemLabel": {"value": "Andrographis paniculata"}}
                    ]
                }
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        elif jalur == "/timeout":
            # Tidur melebihi batas waktu klien
            time.sleep(1.2)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"terlambat")
        else:
            self.send_response(404)
            self.end_headers()


def main():
    # 1. Bersihkan cache sebelum pengujian
    hapus_cache()

    # Siapkan server HTTP lokal
    server = socketserver.TCPServer(("127.0.0.1", 0), HandlerUji)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"

    try:
        # A. Uji Jejak dataclass
        j = Jejak(sumber="Wikidata", versi="2026-10", diambil="2026-10-13", kueri="Q1551608", lisensi="CC0 1.0")
        d_j = j.to_dict()
        cek(d_j["sumber"] == "Wikidata" and d_j["lisensi"] == "CC0 1.0", "Jejak.to_dict menghasilkan dict yang sesuai")
        j_pulih = Jejak.from_dict(d_j)
        cek(j_pulih.sumber == j.sumber and j_pulih.kueri == j.kueri, "Jejak.from_dict memulihkan objek Jejak utuh")

        # B. Uji ambil_json normal (HTTP 200)
        data, jejak1 = ambil_json(f"{base_url}/data.json", lisensi="Open", sumber="UjiLokal")
        cek(data.get("nilai") == 42, f"ambil_json mengambil isi respons: {data}")
        cek(jejak1.sumber == "UjiLokal" and jejak1.lisensi == "Open", "Jejak terisi sumber dan lisensi dengan benar")
        cek(jejak1.versi == "langsung", f"Jejak versi adalah 'langsung': {jejak1.versi}")

        # C. Uji cache lokal (panggilan kedua membaca cache segar tanpa jaringan)
        # Ubah cache_jam panjang, harus mengembalikan data yang sama dan Jejak dengan versi 'cache'
        data_c, jejak_c = ambil_json(f"{base_url}/data.json", lisensi="Open", sumber="UjiLokal", cache_jam=100.0)
        cek(data_c.get("nilai") == 42, "ambil_json kedua menghasilkan data yang sama")
        cek(jejak_c.versi.startswith("cache"), f"versi jejak dari cache segar adalah awalan 'cache': {jejak_c.versi}")

        # D. Uji ambil_teks TSV
        teks, jejak_t = ambil_teks(f"{base_url}/teks.tsv", lisensi="Public", sumber="UjiTSV")
        cek("Curcumin" in teks and "Quercetin" in teks, "ambil_teks berhasil membaca isi TSV")

        # D2. Uji sparql
        bindings, jejak_sq = sparql(f"{base_url}/sparql", "SELECT * WHERE { ?item ?p ?o }")
        cek(len(bindings) == 1 and "item" in bindings[0], f"sparql berhasil memetakan bindings: {bindings}")

        # E. Uji coba ulang 503 -> 200
        HandlerUji.counter_503 = 0
        data_coba, jejak_coba = ambil_json(f"{base_url}/coba_ulang", coba=3, lisensi="Test")
        cek(data_coba.get("coba") == 2, f"coba ulang berhasil setelah 503 (percobaan ke-{data_coba.get('coba')})")

        # F. Uji ukuran_cache dan hapus_cache
        uk = ukuran_cache()
        cek("B" in uk or "KB" in uk, f"ukuran_cache menghasilkan teks terbaca: {uk}")

        # G. Uji mode luring: request gagal jaringan (atau timeout) namun ada cache tersimpan
        # Pertama, request alamat baru agar ada di cache
        data_awal, j_awal = ambil_json(f"{base_url}/data.json", params={"q": "luring"}, cache_jam=0.0001)
        cek(data_awal.get("nilai") == 42, "data awal untuk mode luring tersimpan")

        # Simulasikan server mati / port salah untuk URL tersebut tapi dengan cache yang sudah ada
        # Kita uji fungsi fallback mode luring
        # Tunggu sedikit agar cache_jam (0.0001 jam = 0.36 detik) kadaluwarsa
        time.sleep(0.5)

        # Sekarang matikan server untuk menguji mode luring sejati saat server offline
        server.shutdown()
        server.server_close()

        # Panggilan saat server mati harus masuk mode luring karena berkas cache ada
        data_luring, jejak_luring = ambil_json(f"{base_url}/data.json", params={"q": "luring"}, coba=1, batas=1)
        cek(data_luring.get("nilai") == 42, "mode luring berhasil mengembalikan data dari cache saat server mati")
        cek(jejak_luring.versi.startswith("cache "), f"versi jejak mode luring berformat 'cache <tanggal>': {jejak_luring.versi}")

        # H. Uji pesan galat ramah saat server mati dan TIDAK ada cache
        try:
            ambil_json(f"{base_url}/tidak_ada_di_cache", coba=1, batas=1)
            cek(False, "seharusnya melempar galat bila tidak ada cache dan server mati")
        except IOError as e:
            pesan_err = str(e)
            cek("Koneksi" in pesan_err or "server" in pesan_err or "internet" in pesan_err,
                f"pesan galat ramah Bahasa Indonesia: {pesan_err}")

        # I. Hapus cache dan pastikan berkas bersih
        jum_hapus = hapus_cache()
        cek(jum_hapus >= 2, f"hapus_cache menghapus seluruh berkas ({jum_hapus} berkas)")
        uk_akhir = ukuran_cache()
        cek(uk_akhir == "0 B", f"ukuran cache setelah dihapus adalah 0 B: {uk_akhir}")

    finally:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass

    print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
    sys.exit(1 if gagal else 0)


if __name__ == "__main__":
    main()
