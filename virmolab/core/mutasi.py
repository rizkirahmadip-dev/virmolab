"""Mutasi satu residu pada teks PDB.

Alanin dilakukan di tempat: nama residu menjadi ALA dan atom rantai samping selain CB dibuang.
Residu lain memakai PDBFixer (sudah terpasang bersama OpenMM) bila tersedia.
"""
TIGA = {"A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS", "Q": "GLN", "E": "GLU", "G": "GLY",
        "H": "HIS", "I": "ILE", "L": "LEU", "K": "LYS", "M": "MET", "F": "PHE", "P": "PRO", "S": "SER",
        "T": "THR", "W": "TRP", "Y": "TYR", "V": "VAL"}
TULANG = {"N", "CA", "C", "O", "OXT"}


def ke_alanin(teks, rantai, resi):
    """PDB dengan residu (rantai, resi) menjadi alanin. CB dipertahankan."""
    resi = str(int(resi))
    baris, ada = [], False
    for b in teks.splitlines():
        if b.startswith(("ATOM", "HETATM")) and b[21].strip() == rantai and b[22:26].strip() == resi:
            ada = True
            nama = b[12:16].strip()
            if nama not in TULANG | {"CB"} and not nama.startswith("H"):
                continue
            b = b[:17] + "ALA" + b[20:]
        baris.append(b)
    if not ada:
        raise ValueError(f"Residu {rantai}:{resi} tidak ada di struktur.")
    return "\n".join(baris) + "\n"


def mutasi(teks, rantai, resi, aa):
    """aa = kode satu huruf. Alanin lewat pemotongan; yang lain lewat PDBFixer."""
    aa = aa.strip().upper()
    if aa in TIGA:
        aa = aa
    elif aa in TIGA.values():
        aa = next(k for k, v in TIGA.items() if v == aa)
    else:
        raise ValueError("Asam amino harus kode satu huruf (A, C, D, …) atau nama tiga huruf.")
    if aa == "A":
        return ke_alanin(teks, rantai, resi), "alanin: rantai samping dipotong sampai CB (tanpa relaksasi)"
    try:
        import io
        from pdbfixer import PDBFixer
        from openmm.app import PDBFile
    except Exception as e:
        raise RuntimeError("PDBFixer tidak tersedia untuk mutasi selain alanin.") from e
    f = PDBFixer(pdbfile=io.StringIO(teks))
    # format PDBFixer: 'rantai-resnTiga-nomor-resnBaru' tidak dipakai; API-nya mutasi 'A-30-ALA' pada beberapa versi
    # dan daftar 'rantai-resname-resid-resnamebaru'. Dicoba dua bentuk.
    tujuan = TIGA[aa]
    pola = [f"{rantai}-{resi}-{tujuan}", f"{rantai}-{int(resi)}-{tujuan}"]
    galat = None
    for p in pola:
        try:
            f.applyMutations([p], rantai)
            out = io.StringIO()
            PDBFile.writeFile(f.topology, f.positions, out, keepIds=True)
            return out.getvalue(), f"PDBFixer: {rantai}:{resi} → {tujuan}. Rantai samping belum direlaksasi; " \
                                   "jalankan MM/GBSA atau siapkan ulang bila akan didocking."
        except Exception as e:
            galat = e
            f = PDBFixer(pdbfile=io.StringIO(teks))
    raise RuntimeError(f"PDBFixer menolak mutasi {rantai}:{resi}→{tujuan}: {galat}")
