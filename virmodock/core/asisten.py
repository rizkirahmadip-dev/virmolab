"""Asisten berbahasa Indonesia: catatan tetap di aplikasi, plus Ollama bila pengguna memasangnya.

VirmoDock tidak mengunduh dan tidak membundel model bahasa.
"""
import json
import urllib.request

# (kata kunci, jawaban). Yang pertama cocok dipakai.
_ATURAN = (
    (("ollama", "asisten"),
     "Asisten ini menjawab dari catatan VirmoDock tanpa internet. Bila Ollama sudah berjalan "
     "di komputer ini (alamat 127.0.0.1:11434) dan ada satu model, pertanyaan yang sama juga "
     "dikirim ke model itu. VirmoDock tidak mengunduh model."),
    (("blast", "konservasi", "homolog"),
     "Konservasi diwarnai sebagai persen identitas pada kolom B-faktor. Homolog bisa ditempel, "
     "dicari namanya di UniProt, atau diminta lewat BLAST NCBI pada Swiss-Prot. BLAST mengirim "
     "sekuens ke NCBI. Angka ini bukan skor ConSurf dan bukan probabilitas HMMER."),
    (("gnina", "boltz", "cnn"),
     "GNINA menilai ulang pose yang sudah ada dengan CNN. Boltz-2 memprediksi posisi protein dan ligan. "
     "Keduanya jalan di WSL dan tidak ikut installer Windows. Skor pada berkas kristal yang belum "
     "diprotonasi, atau prediksi tanpa MSA, tidak untuk dikutip sebagai hasil skripsi. MSA lewat "
     "ColabFold hanya jalan bila kotaknya dicentang, dan sekuens ikut terkirim."),
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
     "(--local_only) bila reseptor PDBQT sudah ada. Energi yang muncul adalah skor Vina, bukan CNN."),
    (("grid", "kotak"),
     "Kotak pencarian harus menutupi kantong. Untuk redocking, kotak dipasang di sekeliling ligan kristal."),
    (("skripsi", "mengutip", "sitasi"),
     "Draf Bab III–IV, BibTeX, dan pemeriksa figur ada di Penelitian lanjutan. "
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
