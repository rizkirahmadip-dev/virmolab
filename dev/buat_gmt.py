#!/usr/bin/env python3
"""Alat pengembang: rakit berkas GMT bawaan untuk pengayaan jalur (F3b) -> virmolab/data/gmt/.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/buat_gmt.py

Sumber (diunduh ke dev/gmt_sumber/, tidak ikut Git):
- Reactome ReactomePathways.gmt.zip (CC BY 4.0) -> reactome_manusia.gmt (hanya R-HSA, ukuran set 5-500).
- GO: goa_human.gaf.gz (CC BY 4.0) + go-basic.obo -> go_bp_manusia.gmt. Anotasi Biological Process manusia tanpa
  kualifier NOT dan tanpa kode bukti ND, dipropagasi ke leluhur lewat is_a dan part_of; set berukuran 10-500 gen.
Metadata (versi, tanggal, jumlah set, sha1) ditulis ke virmolab/data/gmt/versi.json.
"""
import gzip
import hashlib
import json
import time
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
SUMBER = AKAR / "dev" / "gmt_sumber"
KELUAR = AKAR / "virmolab" / "data" / "gmt"
URL = {
    "reactome": "https://reactome.org/download/current/ReactomePathways.gmt.zip",
    "goa": "https://current.geneontology.org/annotations/goa_human.gaf.gz",
    "obo": "https://purl.obolibrary.org/obo/go/go-basic.obo",
}


def unduh(kunci):
    SUMBER.mkdir(parents=True, exist_ok=True)
    p = SUMBER / URL[kunci].rsplit("/", 1)[1]
    if not p.exists():
        print("unduh", URL[kunci], flush=True)
        r = urllib.request.Request(URL[kunci], headers={"User-Agent": "VirmoLab-dev/1.0"})
        with urllib.request.urlopen(r, timeout=600) as f:
            p.write_bytes(f.read())
    return p


def reactome():
    z = zipfile.ZipFile(unduh("reactome"))
    teks = z.read(z.namelist()[0]).decode("utf-8")
    baris = []
    for b in teks.splitlines():
        k = b.split("\t")
        if len(k) < 3 or not k[1].startswith("R-HSA-"):
            continue
        gen = sorted(set(x for x in k[2:] if x))
        if 5 <= len(gen) <= 500:
            baris.append("\t".join([k[1], k[0]] + gen))
    return baris


def baca_obo(p):
    nama, induk, ns, usang = {}, defaultdict(set), {}, set()
    cur = None
    for b in p.read_text(encoding="utf-8").splitlines():
        if b == "[Term]":
            cur = {}
        elif b.startswith("[") and b.endswith("]"):
            cur = None
        elif cur is not None and b.startswith("id: GO:"):
            cur["id"] = b[4:]
        elif cur is not None and b.startswith("name: ") and "id" in cur:
            nama[cur["id"]] = b[6:]
        elif cur is not None and b.startswith("namespace: ") and "id" in cur:
            ns[cur["id"]] = b[11:]
        elif cur is not None and b.startswith("is_a: GO:") and "id" in cur:
            induk[cur["id"]].add(b[6:16])
        elif cur is not None and b.startswith("relationship: part_of GO:") and "id" in cur:
            induk[cur["id"]].add(b[22:32])
        elif cur is not None and b == "is_obsolete: true" and "id" in cur:
            usang.add(cur["id"])
    return nama, induk, ns, usang


def go_bp():
    nama, induk, ns, usang = baca_obo(unduh("obo"))
    leluhur_cache = {}

    def leluhur(t):
        if t in leluhur_cache:
            return leluhur_cache[t]
        hasil = {t}
        for i in induk.get(t, ()):
            hasil |= leluhur(i)
        leluhur_cache[t] = hasil
        return hasil

    import sys
    sys.setrecursionlimit(10000)
    set_go = defaultdict(set)
    with gzip.open(unduh("goa"), "rt", encoding="utf-8") as f:
        for b in f:
            if b.startswith("!"):
                continue
            k = b.rstrip("\n").split("\t")
            if len(k) < 15 or k[8] != "P" or "NOT" in k[3] or k[6] == "ND" or k[12] != "taxon:9606":
                continue
            go = k[4]
            if go in usang or ns.get(go) != "biological_process":
                continue
            for t in leluhur(go):
                set_go[t].add(k[2])
    akar = "GO:0008150"     # biological_process (akar) tidak informatif
    baris = []
    for t, gen in sorted(set_go.items()):
        if t != akar and t in nama and 10 <= len(gen) <= 500:
            baris.append("\t".join([t, nama[t]] + sorted(gen)))
    return baris


def tanggal_goa():
    with gzip.open(unduh("goa"), "rt", encoding="utf-8") as f:
        for b in f:
            if b.startswith("!date-generated") or b.startswith("!Generated"):
                return b.split(":", 1)[1].strip()
            if not b.startswith("!"):
                break
    return ""


def versi_obo():
    for b in unduh("obo").read_text(encoding="utf-8").splitlines()[:30]:
        if b.startswith("data-version:"):
            return b.split(":", 1)[1].strip()
    return ""


if __name__ == "__main__":
    KELUAR.mkdir(parents=True, exist_ok=True)
    meta = {}
    for nama_berkas, fungsi, info in (
            ("reactome_manusia.gmt", reactome, {"sumber": "Reactome", "lisensi": "CC BY 4.0", "url": URL["reactome"]}),
            ("go_bp_manusia.gmt", go_bp, {"sumber": "Gene Ontology (GOA manusia, Biological Process)", "lisensi": "CC BY 4.0",
                                          "url": URL["goa"] + " ; " + URL["obo"]})):
        baris = fungsi()
        data = ("\n".join(baris) + "\n").encode("utf-8")
        (KELUAR / nama_berkas).write_bytes(data)
        meta[nama_berkas] = {**info, "n_set": len(baris), "n_gen": len({g for b in baris for g in b.split("\t")[2:]}),
                             "sha1": hashlib.sha1(data).hexdigest()[:12], "dirakit": time.strftime("%Y-%m-%d")}
        print(nama_berkas, meta[nama_berkas], flush=True)
    r = urllib.request.Request("https://reactome.org/ContentService/data/database/version", headers={"User-Agent": "VirmoLab-dev/1.0"})
    meta["reactome_manusia.gmt"]["versi"] = "Reactome v" + urllib.request.urlopen(r, timeout=60).read().decode().strip()
    meta["go_bp_manusia.gmt"]["versi"] = f"GO {versi_obo()}; GOA {tanggal_goa()}"
    (KELUAR / "versi.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
