"""Dialog Sidik jari kontak atom pose (Analisis › Periksa kontak atom pose…).

Menghitung kontak protein–ligan ≤ 4 Å untuk pose yang sedang dianalisis, menandai pose dengan ΔG kuat
tetapi kontak tipis, dan menampilkan rincian pasangan unsur.
"""
from PySide6.QtWidgets import QDialog, QGroupBox, QVBoxLayout

from ..core import rescore_ml
from . import kit

ARTI = {"C-C": "Kontak hidrofobik / van der Waals", "C-HAL": "Halogen pada dinding hidrofobik",
        "N-O": "Kandidat ikatan hidrogen (N reseptor ⋯ O ligan)",
        "O-N": "Kandidat ikatan hidrogen (O reseptor ⋯ N ligan)",
        "O-O": "Pasangan O⋯O: ikatan hidrogen bila ada H, tolakan bila tidak",
        "N-N": "Pasangan N⋯N: ikatan hidrogen bila ada H, tolakan bila tidak",
        "S-C": "Belerang terhadap kerangka karbon", "C-N": "Karbon ⋯ nitrogen", "C-O": "Karbon ⋯ oksigen"}
KOLOM = ["Pasangan (reseptor–ligan)", "Kontak", "Tafsiran"]


class DialogRescoreML(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Kontak atom pose")
        self.resize(820, 640)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul(
            "Sidik jari kontak atom protein–ligan",
            "Semua pasangan atom berat protein–ligan berjarak ≤ 4 Å dihitung per kombinasi unsur (deskriptor gaya "
            "RF-Score), lalu diringkas menjadi skor pembanding dan ukuran kerapatan kontak."))

        self.k_pose = kit.Kartu("Pose")
        self.k_dg = kit.Kartu("ΔG docking")
        self.k_skor = kit.Kartu("Skor kontak")
        lay.addLayout(kit.baris_kartu(self.k_pose, self.k_dg, self.k_skor))
        self.k_total = kit.Kartu("Kontak ≤ 4 Å")
        self.k_rapat = kit.Kartu("Per atom ligan")
        self.k_polar = kit.Kartu("Pangsa kontak polar")
        lay.addLayout(kit.baris_kartu(self.k_total, self.k_rapat, self.k_polar))

        self.l_eval = kit.catatan("", "info")
        lay.addWidget(self.l_eval)

        g = QGroupBox("Rincian pasangan unsur")
        gv = QVBoxLayout(g)
        self.tabel = kit.tabel(KOLOM, regang=2, urut=True)
        gv.addWidget(self.tabel)
        lay.addWidget(g, 1)

        lay.addWidget(kit.catatan(
            "Skor kontak memakai bobot linier sederhana, bukan model Random Forest terlatih PDBbind, dan bukan "
            "pengganti ΔG docking atau MM/GBSA. Pakailah untuk memeringkat pose dalam satu proyek dan menyaring "
            "pose yang kontaknya tipis — jangan dikutip sebagai afinitas terukur."))
        self.l_status = kit.catatan("")
        lay.addLayout(kit.bar_bawah(self, kiri=[kit.tombol("Salin ringkasan", self.salin), self.l_status]))
        self.hitung()

    def hitung(self):
        o = kit.pose_aktif(self.jw)
        teks_rec, nama_rec, _ = kit.reseptor_proyek(self.jw)
        if o is None or not teks_rec:
            self.l_eval.setText("Buka satu pose hasil docking (tab Hasil › klik pose) lalu ulangi.")
            return
        dg = o.info.get("energi")
        try:
            h = rescore_ml.hitung_rescore_ml(teks_rec, o.teks, energi_vina=dg)
        except Exception as e:
            self.l_eval.setText(f"Gagal menghitung kontak: {e}")
            return
        self.hasil = h
        self.k_pose.isi(f"{o.info.get('ligan', o.nama)}", f"{o.nama} · reseptor {nama_rec}")
        self.k_dg.isi(kit.f(dg, 2, "kcal/mol") if dg is not None else "–", o.info.get("mesin", ""))
        self.k_skor.isi(kit.f(h["dG_ml"], 2, "kcal/mol"), f"pKd perkiraan {kit.f(h['pKd'])}")
        self.k_total.isi(str(h["total_kontak"]), f"{h['atom_ligan']} atom berat ligan")
        self.k_rapat.isi(kit.f(h["kontak_per_atom"]),
                         "tipis, pose mungkin menggantung" if h["kontak_per_atom"] < 1.5 else "wajar untuk pose terkubur",
                         nada="warn" if h["kontak_per_atom"] < 1.5 else None)
        self.k_polar.isi(kit.f(h["pangsa_polar"] * 100, 0, "%"), "bagian kontak yang melibatkan N/O kedua sisi")
        self.l_eval.setText(h["evaluasi"])
        kit.ganti_jenis(self.l_eval, "peringatan" if h["peringatan_false_positive"] else "info")
        t = self.tabel
        t.setSortingEnabled(False)
        t.setRowCount(len(h["matriks_kontak"]))
        for r, (k, n) in enumerate(h["matriks_kontak"].items()):
            t.setItem(r, 0, kit.sel(k.replace("HAL", "halogen"), rata_kanan=False))
            t.setItem(r, 1, kit.sel_angka(n, 0))
            t.setItem(r, 2, kit.sel(ARTI.get(k, "Kontak polar / van der Waals"), rata_kanan=False))
        t.setSortingEnabled(True)

    def salin(self):
        h = getattr(self, "hasil", None)
        if not h:
            return
        baris = [f"Kontak <= 4 A: {h['total_kontak']} ({h['kontak_per_atom']} per atom berat ligan)",
                 f"Skor kontak: {h['dG_ml']} kcal/mol (pKd {h['pKd']})",
                 f"dG docking: {h['dG_vina']}", f"Pangsa kontak polar: {h['pangsa_polar']}", h["evaluasi"], ""]
        baris += [f"{k}\t{n}" for k, n in h["matriks_kontak"].items()]
        kit.salin("\n".join(baris), self.l_status, "Ringkasan kontak disalin.")
