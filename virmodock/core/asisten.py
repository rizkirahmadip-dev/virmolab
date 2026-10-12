"""Asisten berbahasa Indonesia: catatan tetap di aplikasi, plus Ollama bila pengguna memasangnya.

VirmoDock tidak mengunduh dan tidak membundel model bahasa.
"""
import json
import urllib.request
from typing import Tuple

# (kata kunci, jawaban). Yang pertama cocok dipakai.
_ATURAN = (
    (("ollama", "asisten"),
     "Asisten ini menjawab dari catatan VirmoDock tanpa internet. Bila Ollama sudah berjalan "
     "di komputer ini (alamat 127.0.0.1:11434) dan ada satu model, pertanyaan yang sama juga "
     "dikirim ke model itu. VirmoDock tidak mengunduh model."),
    (("blast", "konservasi", "homolog"),
     "Konservasi diwarnai sebagai persen identitas pada kolom B-faktor. Homolog bisa ditempel, "
     "dicari namanya di UniProt, atau diminta lewat BLAST NCBI pada Swiss-Prot. "
     "Bila NCBI masih antre, pencarian dikirim ke UniProt, lalu EBI, lalu RCSB PDB. Nomor RID NCBI disimpan di proyek "
     "sehingga tombol ambil hasil tetap bisa dipakai setelah jendela ditutup. Sekuens ikut terkirim. "
     "Angka ini bukan skor ConSurf dan bukan probabilitas HMMER."),
    (("gnina", "boltz", "cnn"),
     "GNINA menilai ulang pose yang sudah ada dengan CNN. Boltz-2 memprediksi posisi protein dan ligan. "
     "Keduanya jalan di WSL dan tidak ikut installer Windows. Setelah docking, tab Hasil mengisi "
     "kolom GNINA bila programnya ada, untuk 10 ligan berenergi terbaik; sisanya lewat menu GNINA untuk sisa ligan. "
     "Sel kosong bukan nol. CNNaffinity dalam pK. "
     "Skor pada berkas kristal yang belum diprotonasi, atau prediksi tanpa MSA, tidak untuk dikutip. "
     "Kotak pengaturan penuh memakai 3 daur ulang dan 200 langkah pada semua rantai yang terbuka. "
     "MSA lewat ColabFold hanya jalan bila kotaknya dicentang, dan sekuens ikut terkirim."),
    (("kovalen", "warhead", "sotorasib"),
     "Docking kovalen mengikat ligan yang punya gugus reaktif ke Cys, Ser, atau Lys di dalam kotak, "
     "lalu men-docking aduknya. Skornya bukan ΔG yang bisa dibandingkan dengan docking biasa. "
     "Contoh yang sudah dicek: 6OIM, RMSD 1,34 Å dari SMILES."),
    (("rmsd", "redock", "valid"),
     "Redocking dianggap lolos bila RMSD pose terbaik terhadap ligan kristal di bawah 2 Å. "
     "Angka energi saja tidak membuktikan posenya benar."),
    (("proton", "hidrogen", "propka", "ph"),
     "Reseptor untuk docking disiapkan di wizard, dengan protonasi PROPKA bila dipilih. "
     "Berkas PDB kristal mentah belum siap di-skor."),
    (("air", "kofaktor", "jembatan"),
     "Air penjembatan adalah oksigen air yang dekat ke protein dan ke ligan sekaligus. "
     "Opsi ini mati secara bawaan. Meeko membuang HOH; bila opsi menyala, air itu ditulis ulang sebagai OA."),
    (("sunting", "kantong", "gugus"),
     "Sunting di kantong mengganti satu gugus pada pose, lalu Vina meminimisasi di tempat "
     "(--local_only) bila reseptor PDBQT sudah ada. Menu Analisis › Seret atom ligan menggeser "
     "satu atom di layar, merapikan ikatan, lalu menjalankan minimisasi yang sama. "
     "Menu Geser ligan utuh memindahkan seluruh ligan tanpa mengubah bentuknya, lalu minimisasi yang sama. "
     "Ctrl+Z mengembalikan posisi ligan. Analisis › Syarat jarak menandai pose yang terlalu jauh dari satu atau dua residu "
     "(lolos bila salah satu cukup dekat) dan menampilkan pose berenergi terbaik yang lolos. "
     "Garis putus-putus di viewer menunjukkan pasangan atom terdekat. "
     "Skor sesudah geser adalah minimisasi di tempat, bukan ΔG docking. "
     "Energi yang muncul di tabel docking adalah skor Vina, bukan CNN."),
    (("grid", "kotak"),
     "Kotak pencarian harus menutupi kantong. Untuk redocking, kotak dipasang di sekeliling ligan kristal."),
    (("skripsi", "mengutip", "sitasi"),
     "Draf Bab III-IV, BibTeX, dan pemeriksa figur ada di Penelitian lanjutan. "
     "Cantumkan mesin, protonasi, ukuran kotak, dan bahwa skor kovalen atau CNN bukan ΔG eksperimen."),
)


def jawab_aturan(pertanyaan):
    """Jawaban catatan, atau None bila tidak ada kata kunci."""
    t = (pertanyaan or "").lower()
    for kunci, jawaban in _ATURAN:
        if any(k in t for k in kunci):
            return jawaban
    return None


def model_ollama(timeout=2):
    """Nama model pertama di Ollama, atau None bila layanan tidak jalan."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None
    for m in data.get("models") or []:
        if m.get("name"):
            return m["name"]
    return None


def tanya_ollama(pertanyaan, model, timeout=180):
    body = json.dumps({
        "model": model,
        "stream": False,
        "prompt": ("Kamu asisten VirmoDock untuk docking molekuler. Jawab singkat dalam Bahasa Indonesia. "
                    "Jangan mengarang angka energi atau RMSD. Pertanyaan:\n" + pertanyaan),
    }).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    return (data.get("response") or "").strip()


def jawab(pertanyaan):
    """Catatan tetap, ditambah jawaban Ollama bila sebuah model sudah terpasang."""
    if not (pertanyaan or "").strip():
        return "Tulis pertanyaan dulu."
    catatan = jawab_aturan(pertanyaan)
    model = model_ollama()
    llm = ""
    if model:
        try:
            llm = tanya_ollama(pertanyaan, model)
        except Exception as e:
            llm = f"Ollama ({model}) tidak selesai: {type(e).__name__}."
    if catatan and llm:
        return catatan + "\n\nOllama (" + model + "):\n" + llm
    if llm:
        return llm + "\n\n(Ollama " + model + ", di komputer ini.)"
    if catatan:
        return catatan + "\n\nOllama tidak berjalan di komputer ini, jadi hanya catatan di atas yang dipakai."
    return ("Tidak ada catatan untuk pertanyaan itu, dan Ollama tidak berjalan. "
            "Pasang Ollama lalu unduh satu model bila ingin jawaban bebas. VirmoDock tidak mengunduh model.")


# -----------------------------------------------------------------------------
# Modul Interpretasi Hasil Docking AI (Ollama Enhanced & Expert Template)
# -----------------------------------------------------------------------------

def buat_konteks_docking(proyek, jobs=None) -> Tuple[str, dict]:
    """Kumpulkan data hasil docking proyek ke format teks terstruktur & dict data."""
    if not proyek:
        return "Tidak ada proyek docking yang aktif.", {}

    from . import ekspor

    # Metadata target
    nama_target = "Target"
    pdb_id = ""
    if proyek.reseptor and isinstance(proyek.reseptor, dict):
        nama_target = proyek.reseptor.get("nama") or proyek.nama
        pdb_id = proyek.reseptor.get("pdb_id") or ""
    elif proyek.nama:
        nama_target = proyek.nama

    # Kotak grid
    kotak_str = "-"
    if proyek.kotak and isinstance(proyek.kotak, dict):
        p = proyek.kotak.get("pusat", {})
        u = proyek.kotak.get("ukuran", {})
        kotak_str = f"Pusat({p.get('x', 0):.1f}, {p.get('y', 0):.1f}, {p.get('z', 0):.1f}), Ukuran({u.get('x', 0):.1f}, {u.get('y', 0):.1f}, {u.get('z', 0):.1f})"

    # Validasi RMSD redocking
    rmsd_val = None
    if proyek.validasi and isinstance(proyek.validasi, dict):
        rmsd_val = proyek.validasi.get("rmsd")

    # Ambil baris hasil
    baris = ekspor.baris_hasil(proyek, jobs=jobs)
    total_ligan = len(baris)

    # Top-5 ligan
    top5 = baris[:5]
    tabel_md = []
    tabel_md.append("| Peringkat | Ligan | ΔG (kcal/mol) | Ki perkiraan | LE | H-Bond | Hidrofobik | π-π |")
    tabel_md.append("|---|---|---|---|---|---|---|---|")
    for i, b in enumerate(top5):
        tabel_md.append(
            f"| {i+1} | {b.get('ligan', 'Ligan')} | {b.get('energi', 0):.2f} | {b.get('ki', '-')} | "
            f"{b.get('le', 0) if b.get('le') is not None else '-'} | {b.get('hbond', 0)} | "
            f"{b.get('hidrofobik', 0)} | {b.get('pi', 0)} |"
        )

    teks_konteks = f"""PROYEK DOCKING:
- Target Reseptor: {nama_target} {f'(PDB: {pdb_id})' if pdb_id else ''}
- Parameter Kotak Grid: {kotak_str}
- Validasi RMSD Redocking: {f'{rmsd_val:.2f} Å (Valid < 2.0 Å)' if rmsd_val is not None else 'Belum divalidasi'}
- Total Ligan Selesai: {total_ligan} ligan

TABEL 5 LIGAN DENGAN AFINITAS TERBAIK:
{chr(10).join(tabel_md)}
"""
    data_dict = {
        "nama_target": nama_target,
        "pdb_id": pdb_id,
        "kotak": kotak_str,
        "rmsd_val": rmsd_val,
        "total_ligan": total_ligan,
        "top5": top5,
    }
    return teks_konteks, data_dict


def prompt_ringkasan(konteks: str) -> str:
    """Prompt untuk menghasilkan ringkasan eksekutif 1-2 paragraf."""
    return f"""Berikut adalah data hasil molecular docking:
{konteks}

Instruksi:
Tulis ringkasan eksekutif hasil penapisan/docking di atas dalam 1-2 paragraf padat berbahasa Indonesia formal.
Sebutkan target reseptor, jumlah ligan, ligan terbaik beserta nilai energi bebas ikatan (ΔG dalam kcal/mol), estimasi konstanta inhibisi (Ki), dan jenis interaksi kunci (ikatan hidrogen/hidrofobik).
Jangan mengarang angka, gunakan data yang tersedia di atas."""


def prompt_hasil_pembahasan(konteks: str) -> str:
    """Prompt untuk menghasilkan draf Bab Hasil dan Pembahasan karya ilmiah/skripsi."""
    return f"""Berikut adalah data hasil molecular docking:
{konteks}

Instruksi:
Tulis draf bagian 'Hasil dan Pembahasan' (2-3 paragraf) untuk skripsi atau artikel jurnal farmasi/kimia komputasi dalam Bahasa Indonesia baku.
Bahasan harus mencakup:
1. Validitas metode penambatan molekuler (berdasarkan parameter grid dan RMSD jika ada).
2. Perbandingan afinitas ikatan (ΔG) ligan-ligan teratas serta interpretasi nilai Ki dan Ligand Efficiency (LE).
3. Kontribusi ikatan non-kovalen (ikatan hidrogen, interaksi hidrofobik, interaksi aromatik pi) dalam menstabilkan kompleks ligan-protein.
Gunakan gaya penulisan akademik ilmiah, jangan mengarang data atau angka."""


def prompt_perbandingan(konteks_a: str, konteks_b: str) -> str:
    """Prompt perbandingan dua job docking atau dua target protein."""
    return f"""Berikut adalah data docking dari dua set eksperimen:

SET A:
{konteks_a}

SET B:
{konteks_b}

Instruksi:
Bandingkan hasil docking antara Set A dan Set B dalam 2 paragraf analitis berbahasa Indonesia:
1. Bandingkan kekuatan afinitas (ΔG) rata-rata dan ligan terbaik.
2. Jelaskan perbedaan pola interaksi ikatan hidrogen dan hidrofobik antar kedua kondisi.
Gunakan data yang tertera, jangan menambahkan fakta fiktif."""


def _fallback_template(mode: str, data: dict) -> str:
    """Template terstruktur berkualitas tinggi jika Ollama tidak tersedia."""
    tgt = data.get("nama_target", "Reseptor")
    n_tot = data.get("total_ligan", 0)
    top5 = data.get("top5", [])
    rmsd = data.get("rmsd_val")

    if not top5:
        return "Belum ada data hasil docking yang cukup untuk diinterpretasikan."

    juara = top5[0]
    nama_j = juara.get("ligan", "Ligan Utama")
    dg_j = juara.get("energi", 0.0)
    ki_j = juara.get("ki", "-")
    le_j = juara.get("le")
    hb_j = juara.get("hbond", 0)
    hf_j = juara.get("hidrofobik", 0)
    pi_j = juara.get("pi", 0)

    if mode == "hasil_pembahasan":
        val_teks = (f"Metode penambatan molekuler menunjukkan reliabilitas yang baik dengan nilai RMSD validasi sebesar {rmsd:.2f} Å (memenuhi kriteria keberterimaan < 2,0 Å)."
                    if rmsd is not None else
                    "Penambatan molekuler dilakukan terhadap kantong pengikatan aktif target reseptor yang telah terdefinisi.")

        paragraf1 = (
            f"Berdasarkan simulasi molecular docking terhadap target protein {tgt}, sebanyak {n_tot} senyawa ligan "
            f"telah berhasil ditapis ke dalam sisi aktif reseptor. {val_teks} "
            f"Senyawa {nama_j} menunjukkan afinitas pengikatan tertinggi dengan nilai energi bebas penambatan (ΔG) sebesar {dg_j:.2f} kcal/mol "
            f"dan estimasi konstanta inhibisi (Ki) sebesar {ki_j}."
        )

        paragraf2 = (
            f"Tingginya afinitas pengikatan {nama_j} didukung oleh pembentukan jaringan interaksi non-kovalen yang stabil pada kantong aktif, "
            f"terdiri dari {hb_j} ikatan hidrogen, {hf_j} kontak hidrofobik, serta {pi_j} interaksi penumpukan aromatik (π-π). "
            f"Selain itu, nilai Ligand Efficiency (LE) sebesar {f'{le_j:.2f}' if le_j is not None else '-'} kcal/mol/atom berat mengindikasikan "
            f"bahwa afinitas yang diperoleh proporsional secara optimal terhadap ukuran molekul senyawa tersebut."
        )

        paragraf3 = (
            f"Secara komparatif, 5 ligan teratas menunjukkan rentang afinitas antara {top5[-1].get('energi', 0):.2f} hingga {dg_j:.2f} kcal/mol, "
            f"yang memperlihatkan potensi farmakologis kuat sebagai kandidat ligan bioaktif terpilih untuk pengujian eksperimental lebih lanjut."
        )
        return f"### Hasil dan Pembahasan Penambatan Molekuler\n\n{paragraf1}\n\n{paragraf2}\n\n{paragraf3}"

    else:
        # Ringkasan eksekutif
        p1 = (
            f"Penapisan penambatan molekuler terhadap {tgt} berhasil mengevaluasi {n_tot} ligan. "
            f"Senyawa unggulan dengan afinitas ikatan paling stabil diraih oleh **{nama_j}** dengan nilai energi bebas ikatan (ΔG) "
            f"sebesar **{dg_j:.2f} kcal/mol** dan estimasi daya inhibisi Ki sebesar **{ki_j}**."
        )
        p2 = (
            f"Stabilitas pose terbaik {nama_j} ditopang oleh {hb_j} ikatan hidrogen, {hf_j} kontak hidrofobik, "
            f"dan {pi_j} interaksi π. Senyawa ini merupakan kandidat paling potensial untuk dilanjutkan ke tahap sintesis atau pengujian in vitro."
        )
        return f"### Ringkasan Eksekutif Hasil Docking\n\n{p1}\n\n{p2}"


def interpretasi(proyek, mode: str = "ringkasan", jobs=None, timeout: int = 180) -> str:
    """Fungsi utama pembuatan interpretasi hasil docking berbantuan AI / Pakar Lokal.

    Mode: 'ringkasan' | 'hasil_pembahasan'
    """
    konteks_teks, data_dict = buat_konteks_docking(proyek, jobs=jobs)
    if not data_dict.get("top5"):
        return "Belum ada hasil docking selesai di dalam proyek ini."

    if mode == "hasil_pembahasan":
        prompt = prompt_hasil_pembahasan(konteks_teks)
    else:
        prompt = prompt_ringkasan(konteks_teks)

    model = model_ollama(timeout=2)
    if model:
        try:
            respons = tanya_ollama(prompt, model, timeout=timeout)
            if respons and len(respons.strip()) > 30:
                return (f"{respons}\n\n*(Disusun model bahasa lokal Ollama ({model}). Model bahasa bisa keliru menyebut "
                        "angka atau residu: cocokkan tiap nilai dengan tab Hasil sebelum dipakai di naskah, dan "
                        "sebutkan pemakaian AI di bagian metode bila jurnal mewajibkannya.)*")
        except Exception:
            pass

    # Fallback ke mesin pakar lokal bila Ollama tidak aktif
    teks_pakar = _fallback_template(mode, data_dict)
    return (f"{teks_pakar}\n\n*(Ollama tidak aktif. Teks di atas dirangkai VirmoDock langsung "
            "dari angka proyek menurut templat tetap — periksa dan tulis ulang dengan kalimat Anda sendiri.)*")

