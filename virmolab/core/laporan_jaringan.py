"""Laporan farmakologi jaringan yang lengkap, beserta statistik pendukungnya.

Dua hal yang dikerjakan di sini:

1. **Statistik.** Memakai mesin uji VirmoLab yang sudah ada (`core.uji`) alih-alih menghitung sendiri,
   sehingga pemilihan uji, pemeriksaan asumsi, ukuran efek, dan kalimat metodenya sama persis dengan
   bagian aplikasi yang lain. Dua hal diuji: apakah senyawa yang lolos penyaringan memang berbeda
   sifat fisikokimianya dari yang gugur, dan bagaimana sebaran topologi jaringan PPI-nya.
2. **Laporan.** Satu dokumen HTML bertabel yang bisa langsung dibaca peneliti: apa yang dikerjakan,
   dengan parameter apa, hasilnya berapa, apa artinya, dan apa batasnya. HTML-nya sengaja sederhana
   (tabel dan gaya sebaris) karena dirender `QTextDocument` untuk dicetak ke PDF dan diurai
   `core.docx_ringan` untuk Word — keduanya hanya mendukung sebagian kecil CSS.

Laporan ini memuat bagian Keterbatasan yang tidak bisa dihapus. Hasil farmakologi jaringan adalah
hipotesis dari penambangan basis data; naskah yang memuatnya tanpa menyebut batasnya menyesatkan.
"""
import html as H
import math
from typing import Any, Dict, List, Optional, Sequence

from . import farmakologi as F, jaringan, uji

SIFAT_DIUJI = [("mw", "Massa molekul (g/mol)"), ("wlogp", "WLOGP"), ("tpsa", "TPSA (Å²)"),
               ("qed", "QED"), ("sascore", "SA Score")]


def _a(v, d=2) -> str:
    """Angka gaya Indonesia; '–' bila kosong."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    if isinstance(v, (int,)) or (isinstance(v, float) and float(v).is_integer() and abs(v) < 1e6 and d == 0):
        return str(int(v))
    return f"{float(v):.{d}f}".replace(".", ",")


# ------------------------------------------------------------------ statistik
def statistik_sifat(senyawa: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Bandingkan sifat fisikokimia senyawa yang lolos penyaringan dengan yang gugur.

    Dilaporkan karena menjawab pertanyaan yang wajar ditanyakan pembaca: penyaringan ADMET itu
    membuang apa? Bila tidak ada beda bermakna pada satu sifat pun, penyaringannya bekerja lewat
    kriteria lain (mis. prediksi toksisitas), bukan lewat ukuran atau lipofilisitas molekulnya.
    Uji dipilih otomatis oleh core.uji (Welch bila normal, Mann-Whitney bila tidak).
    """
    lolos = [s for s in senyawa if s.get("lolos") and s.get("sifat")]
    gugur = [s for s in senyawa if not s.get("lolos") and s.get("sifat")]
    if len(lolos) < 3 or len(gugur) < 3:
        return []
    hasil = []
    for kunci, label in SIFAT_DIUJI:
        a = uji.bersihkan([s["sifat"].get(kunci) for s in lolos])
        b = uji.bersihkan([s["sifat"].get(kunci) for s in gugur])
        if len(a) < 3 or len(b) < 3:
            continue
        h = uji.analisis([a, b], ["Lolos", "Gugur"])
        if "p" not in h:
            continue
        hasil.append({"sifat": label, "n_lolos": len(a), "n_gugur": len(b),
                      "rerata_lolos": h["deskriptif"][0]["rerata"], "sd_lolos": h["deskriptif"][0]["sd"],
                      "rerata_gugur": h["deskriptif"][1]["rerata"], "sd_gugur": h["deskriptif"][1]["sd"],
                      "nama_uji": h.get("nama_uji", ""), "p": h["p"],
                      "efek": h.get("efek"), "interpretasi": h.get("interpretasi", ""),
                      "metode": h.get("metode", "")})
    return hasil


def topologi(G) -> Dict[str, Any]:
    """Ringkasan topologi jaringan PPI: ukuran, kerapatan, derajat, klaster, dan komponen.

    Angka-angka ini yang biasanya diminta pembahas: jaringan padat atau renggang, apakah ada sedikit
    simpul berderajat sangat tinggi (ciri jaringan bebas skala), dan apakah jaringannya terhubung
    sebagai satu kesatuan atau terpecah.
    """
    import networkx as nx
    if G is None or G.number_of_nodes() == 0:
        return {}
    derajat = [d for _n, d in G.degree()]
    des = uji.deskriptif(derajat) if derajat else {}
    komponen = list(nx.connected_components(G))
    terbesar = max((len(c) for c in komponen), default=0)
    return {
        "simpul": G.number_of_nodes(),
        "tepi": G.number_of_edges(),
        "kerapatan": nx.density(G),
        "derajat_rerata": des.get("rerata"),
        "derajat_sd": des.get("sd"),
        "derajat_median": des.get("median"),
        "derajat_maks": des.get("maks"),
        "klaster": nx.average_clustering(G) if G.number_of_nodes() > 2 else None,
        "komponen": len(komponen),
        "komponen_terbesar": terbesar,
        "bagian_terbesar": terbesar / G.number_of_nodes() if G.number_of_nodes() else None,
        "terpencil": sum(1 for d in derajat if d == 0),
    }


def teks_topologi(t: Dict[str, Any]) -> str:
    """Satu paragraf pembacaan angka topologi, bukan sekadar daftar."""
    if not t:
        return ""
    bagian = [f"Jaringan memuat {t['simpul']} simpul dan {t['tepi']} tepi dengan kerapatan "
              f"{_a(t.get('kerapatan'), 3)}."]
    if t.get("derajat_rerata") is not None:
        bagian.append(f"Derajat rata-rata {_a(t['derajat_rerata'])} (SD {_a(t.get('derajat_sd'))}, "
                      f"median {_a(t.get('derajat_median'))}, tertinggi {_a(t.get('derajat_maks'), 0)}).")
        if t.get("derajat_median") and t["derajat_maks"] and t["derajat_maks"] >= 3 * max(t["derajat_median"], 1):
            bagian.append("Simpul berderajat tertinggi jauh melampaui median, pola yang lazim pada jaringan "
                          "biologis: sedikit protein memegang sebagian besar hubungan.")
    if t.get("klaster") is not None:
        bagian.append(f"Koefisien klaster rata-rata {_a(t['klaster'], 3)}.")
    if t.get("komponen", 0) > 1:
        bagian.append(f"Jaringan terpecah menjadi {t['komponen']} komponen; komponen terbesar memuat "
                      f"{t['komponen_terbesar']} simpul ({_a((t.get('bagian_terbesar') or 0) * 100, 1)} %).")
    else:
        bagian.append("Seluruh simpul berada dalam satu komponen terhubung.")
    if t.get("terpencil"):
        bagian.append(f"{t['terpencil']} protein tidak punya tepi pada ambang ini; ketiadaan tepi bisa berarti "
                      f"ambangnya terlalu tinggi, bukan berarti proteinnya tidak berperan.")
    return " ".join(bagian)


# ------------------------------------------------------------------ laporan
def _tabel(kolom: Sequence[str], baris: Sequence[Sequence[Any]], rata_kanan: Sequence[int] = ()) -> str:
    o = ['<table width="100%" cellspacing="0" cellpadding="4" border="0">',
         '<tr>' + "".join(
             f'<th align="{"right" if i in rata_kanan else "left"}" '
             f'style="background:#eef2f7;border-bottom:1px solid #c9d3e0">{H.escape(str(k))}</th>'
             for i, k in enumerate(kolom)) + "</tr>"]
    for r in baris:
        o.append("<tr>" + "".join(
            f'<td align="{"right" if i in rata_kanan else "left"}" '
            f'style="border-bottom:1px solid #eceff3">{v if isinstance(v, str) and v.startswith("<") else H.escape(str(v))}</td>'
            for i, v in enumerate(r)) + "</tr>")
    o.append("</table>")
    return "\n".join(o)


def _judul(n: int, teks: str) -> str:
    return f'<h2 style="color:#204f8f">{n}. {H.escape(teks)}</h2>'


def html(k: Dict[str, Any], G=None, info: Optional[Dict[str, Any]] = None) -> str:
    """Laporan lengkap sebagai HTML sederhana (siap dicetak PDF atau diubah ke Word)."""
    info = info or {}
    sen = k.get("senyawa") or []
    lolos = F.yang_lolos(sen)
    target = k.get("target_senyawa") or {}
    gen_target = sorted({g for d in target.values() for g in d})
    gen_penyakit = k.get("gen_penyakit") or []
    irisan = k.get("irisan") or []
    hub = k.get("hub") or []
    jalur = k.get("jalur") or []
    penyakit = (k.get("penyakit") or {}).get("nama") or "penyakit yang diteliti"
    tanaman = k.get("tanaman") or "sumber senyawa"
    ambang = k.get("ambang_string", jaringan.AMBANG_STRING)

    o = ['<h1 style="color:#173b6c">Laporan farmakologi jaringan</h1>',
         f'<p style="color:#465263">{H.escape(tanaman)} terhadap {H.escape(penyakit)}'
         + (f' · {H.escape(str(info.get("tanggal")))}' if info.get("tanggal") else "") + "</p>",
         '<p style="background:#fdf6e3;padding:8px;border:1px solid #e0d5b0">'
         'Seluruh angka dalam laporan ini adalah hipotesis komputasi hasil penambangan basis data, '
         'bukan bukti aktivitas biologis. Lihat bagian Keterbatasan.</p>']

    # 1. Ringkasan
    o.append(_judul(1, "Ringkasan"))
    o.append(_tabel(["Tahap", "Hasil", "Satuan", "Keterangan"],
                    [[r["tahap"], _a(r["nilai"], 0), r["satuan"], r["ket"]] for r in F.ringkasan(k)],
                    rata_kanan=(1,)))

    # 2. Metode
    o.append(_judul(2, "Metode"))
    o.append(f"<p>{H.escape(F.paragraf_metode(k))}</p>")

    # 3. Senyawa
    o.append(_judul(3, "Senyawa yang dianalisis"))
    o.append(f"<p>Sebanyak {len(sen)} senyawa dikumpulkan dari {H.escape(tanaman)}. "
             f"Sepuluh pertama ditampilkan di sini; daftar lengkapnya ada pada lampiran JSON.</p>")
    o.append(_tabel(["Senyawa", "MW", "WLOGP", "TPSA", "Lipinski", "Status"],
                    [[s["nama"], _a((s.get("sifat") or {}).get("mw"), 1),
                      _a((s.get("sifat") or {}).get("wlogp")), _a((s.get("sifat") or {}).get("tpsa"), 1),
                      _a((s.get("sifat") or {}).get("lipinski"), 0),
                      "Lolos" if s.get("lolos") else "Gugur"] for s in sen[:10]],
                    rata_kanan=(1, 2, 3, 4)))

    # 4. Penyaringan + statistik
    o.append(_judul(4, "Penyaringan ADMET"))
    n_gugur = len(sen) - len(lolos)
    o.append(f"<p>Sebanyak {len(lolos)} dari {len(sen)} senyawa lolos penyaringan, sedangkan {n_gugur} lainnya "
             f"gugur. Alasan pengguguran dicatat untuk tiap senyawa.</p>")
    # Dikelompokkan menurut kode kriteria yang ditulis saring(), bukan menurut potongan kalimatnya:
    # "DILI 0,85 > 0,70" dan "DILI 0,91 > 0,70" adalah alasan yang sama dan harus dihitung bersama.
    alasan: Dict[str, int] = {}
    for s in sen:
        for kd in dict.fromkeys(s.get("alasan_kode") or []):
            label = F.LABEL_ALASAN.get(kd, kd)
            alasan[label] = alasan.get(label, 0) + 1
    if alasan:
        o.append("<h3>Alasan pengguguran</h3>")
        o.append(_tabel(["Alasan", "Jumlah senyawa", "Persen dari yang gugur"],
                        [[a, n, _a(100 * n / max(n_gugur, 1), 1) + " %"]
                         for a, n in sorted(alasan.items(), key=lambda r: -r[1])],
                        rata_kanan=(1, 2)))
        o.append("<p>Satu senyawa dapat gugur karena lebih dari satu alasan, sehingga jumlah pada "
                 "tabel ini bisa melampaui jumlah senyawa yang gugur.</p>")
    stat = statistik_sifat(sen)
    if stat:
        o.append("<h3>Perbandingan sifat: lolos berbanding gugur</h3>")
        o.append(_tabel(["Sifat", "Lolos (rerata ± SD)", "Gugur (rerata ± SD)", "Uji", "p"],
                        [[r["sifat"], f"{_a(r['rerata_lolos'])} ± {_a(r['sd_lolos'])}",
                          f"{_a(r['rerata_gugur'])} ± {_a(r['sd_gugur'])}", r["nama_uji"],
                          uji.f_p(r["p"]) + " " + uji.bintang(r["p"])] for r in stat]))
        bermakna = [r for r in stat if r["p"] < 0.05]
        o.append(f"<p>{'Sifat yang berbeda bermakna: ' + ', '.join(r['sifat'] for r in bermakna) + '.' if bermakna else 'Tidak ada sifat fisikokimia yang berbeda bermakna antara kedua kelompok; penyaringan bekerja lewat kriteria prediksi ADMET, bukan lewat ukuran atau lipofilisitas molekulnya.'}</p>")
        if stat:
            o.append(f'<p style="color:#465263">{H.escape(stat[0]["metode"])}</p>')

    # 5. Target
    o.append(_judul(5, "Target senyawa"))
    o.append(f"<p>Target dugaan ditetapkan melalui {H.escape(F.label_sumber(k.get('sumber_target') or []))}, "
             f"menghasilkan {len(gen_target)} simbol gen unik dari {len(target)} senyawa yang memberikan hasil "
             f"pencarian.</p>")
    o.append(_tabel(["Senyawa", "Jumlah target", "Gen (10 pertama)"],
                    [[n, len(g), ", ".join(g[:10])] for n, g in
                     sorted(target.items(), key=lambda x: -len(x[1]))[:12]], rata_kanan=(1,)))

    # 6. Gen penyakit dan irisan
    o.append(_judul(6, "Gen penyakit dan target terapi potensial"))
    o.append(f"<p>Sebanyak {len(gen_penyakit)} gen berasosiasi dengan {H.escape(penyakit)} menurut "
             f"{H.escape((k.get('penyakit') or {}).get('sumber') or 'sumber yang dipakai')}. "
             f"Irisan antara kedua himpunan itu menghasilkan {len(irisan)} target terapi potensial.</p>")
    if irisan:
        o.append(f"<p><b>Target terapi potensial:</b> {H.escape(', '.join(irisan))}</p>")

    # 7. Jaringan
    o.append(_judul(7, "Jaringan interaksi protein–protein"))
    t = topologi(G) if G is not None else {}
    if t:
        o.append(f"<p>{H.escape(teks_topologi(t))}</p>")
        o.append(_tabel(["Ukuran", "Nilai"],
                        [["Simpul", _a(t["simpul"], 0)], ["Tepi", _a(t["tepi"], 0)],
                         ["Kerapatan", _a(t.get("kerapatan"), 3)],
                         ["Derajat rata-rata", _a(t.get("derajat_rerata"))],
                         ["Derajat tertinggi", _a(t.get("derajat_maks"), 0)],
                         ["Koefisien klaster", _a(t.get("klaster"), 3)],
                         ["Komponen terhubung", _a(t.get("komponen"), 0)]], rata_kanan=(1,)))
    else:
        o.append(f"<p>Jaringan diambil dari STRING pada ambang skor gabungan ≥ {_a(ambang, 2)} "
                 f"dan memuat {len(k.get('tepi_ppi') or [])} tepi.</p>")
    if hub:
        o.append("<h3>Protein hub</h3>")
        o.append("<p>Protein hub diperingkat dengan Maximal Clique Centrality (MCC), metode cytoHubba yang "
                 "pada pengujian aslinya paling tepat menemukan protein esensial. Derajat, betweenness, "
                 "dan closeness disertakan sebagai pembanding.</p>")
        o.append(_tabel(["Peringkat", "Gen", "MCC", "Derajat", "Betweenness", "Closeness"],
                        [[i + 1, b["gen"], _a(b["mcc"], 1), _a(b["derajat"], 0),
                          _a(b["betweenness"], 4), _a(b["closeness"], 4)] for i, b in enumerate(hub[:10])],
                        rata_kanan=(0, 2, 3, 4, 5)))

    # 8. Jalur
    o.append(_judul(8, "Pengayaan jalur"))
    if jalur:
        gmt = {"reactome": "Reactome", "go_bp": "Gene Ontology Biological Process"}.get(k.get("gmt"), k.get("gmt"))
        o.append(f"<p>Pengayaan terhadap set gen {H.escape(str(gmt))} memakai uji hipergeometrik satu sisi "
                 f"dengan koreksi Benjamini-Hochberg. Sebanyak {len(jalur)} jalur dilaporkan, dan "
                 f"{sum(1 for b in jalur if (b.get('q') or 1) <= 0.05)} di antaranya memiliki q ≤ 0,05.</p>")
        o.append(_tabel(["Jalur", "Gen", "Ukuran set", "p", "q", "Gen yang terlibat"],
                        [[b["nama"], _a(b["n_overlap"], 0), _a(b["n_set"], 0), uji.f_p(b["p"]),
                          uji.f_p(b.get("q") or 1), ", ".join((b.get("gen") or [])[:8])]
                         for b in jalur[:15]], rata_kanan=(1, 2, 3, 4)))
    else:
        o.append("<p>Pengayaan jalur belum dijalankan.</p>")

    # 9. Keterbatasan
    o.append(_judul(9, "Keterbatasan"))
    o.append("<ol>"
             "<li><b>Bergantung pada kelengkapan basis data publik.</b> Senyawa tanaman yang belum "
             "terdaftar atau belum banyak diteliti tidak akan muncul, dan gen yang banyak dipelajari "
             "cenderung lebih sering tampil sebagai target utama.</li>"
             "<li><b>Dosis tidak diperhitungkan.</b> Interaksi dimodelkan secara kualitatif; apakah kadar "
             "senyawa di dalam tubuh cukup untuk menimbulkan efek terapi tidak ikut diprediksi.</li>"
             "<li><b>Pencernaan dan metabolisme diabaikan.</b> Analisis memakai senyawa asli dari tanaman, "
             "padahal zat itu diubah oleh usus dan hati menjadi metabolit yang bentuk dan fungsinya bisa "
             "sangat berbeda.</li>"
             "<li><b>Arah interaksi tidak diketahui.</b> Data menunjukkan hubungan senyawa dengan protein, "
             "tanpa menjelaskan apakah sifatnya menghambat atau justru mengaktifkan.</li>"
             "<li><b>Waktu dan lokasi diabaikan.</b> Sistem tubuh berubah dan berbeda di tiap organ, "
             "sedangkan analisis ini memperlakukannya sebagai gambar diam.</li>"
             "<li><b>Tepi STRING bukan hanya interaksi fisik.</b> Skornya memadukan eksperimen, basis data "
             "terkurasi, penambangan teks, ko-ekspresi, dan kedekatan gen; dua protein bisa terhubung "
             "tanpa pernah bersentuhan.</li>"
             "</ol>"
             "<p>Karena itu hasil ini berfungsi sebagai penyaring awal untuk menghemat waktu dan biaya. "
             "Pembuktian tetap memerlukan pengujian pada sel atau hewan uji.</p>")

    # 10. Sumber data
    jejak = info.get("jejak") or []
    if jejak:
        o.append(_judul(10, "Sumber data"))
        o.append(_tabel(["Sumber", "Versi", "Diambil", "Lisensi"],
                        [[j.get("sumber", ""), j.get("versi", ""), (j.get("diambil", "") or "")[:10],
                          j.get("lisensi", "")] for j in jejak[:25]]))
    return "\n".join(o)
