"""Penulis .docx ringan (Office Open XML) tanpa pustaka tambahan.

Mengubah HTML sederhana dari laporan.html() ke dokumen Word yang bisa disunting: h1/h2, p, b/strong,
span (kelas ok/bad/warn/mut -> warna), table (th -> sel berlatar, td.n -> rata kanan), img (PNG, dari kamus
gambar), ol/ul/li, br. Tag lain diabaikan (isi teksnya tetap ikut).
"""
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from xml.sax.saxutils import escape

WARNA = {"ok": "2E9E5B", "bad": "CF3F3F", "warn": "C98A12", "mut": "7B8698"}
EMU_CM = 360000

_TIPE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""
_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""
_GAYA = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri" w:eastAsia="Calibri"/>
<w:sz w:val="20"/><w:szCs w:val="20"/><w:lang w:val="id-ID"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="0" w:after="60"/><w:outlineLvl w:val="0"/></w:pPr>
<w:rPr><w:b/><w:color w:val="173B6C"/><w:sz w:val="34"/><w:szCs w:val="34"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="280" w:after="80"/><w:pBdr><w:bottom w:val="single" w:sz="4" w:space="1" w:color="D3D9E1"/></w:pBdr><w:outlineLvl w:val="1"/></w:pPr>
<w:rPr><w:b/><w:color w:val="173B6C"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:rPr><w:i/><w:color w:val="5B6B82"/><w:sz w:val="18"/></w:rPr></w:style>
<w:style w:type="table" w:styleId="TabelLaporan"><w:name w:val="Tabel Laporan"/><w:tblPr>
<w:tblBorders><w:top w:val="single" w:sz="4" w:color="D3D9E1"/><w:left w:val="single" w:sz="4" w:color="D3D9E1"/>
<w:bottom w:val="single" w:sz="4" w:color="D3D9E1"/><w:right w:val="single" w:sz="4" w:color="D3D9E1"/>
<w:insideH w:val="single" w:sz="4" w:color="D3D9E1"/><w:insideV w:val="single" w:sz="4" w:color="D3D9E1"/></w:tblBorders>
<w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>
</w:styles>"""
_NOMOR = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/>
<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="400" w:hanging="400"/></w:pPr></w:lvl></w:abstractNum>
<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/>
<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="400" w:hanging="300"/></w:pPr></w:lvl></w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>"""
_NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
       'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
       'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
       'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')


def ukuran_png(data):
    """Lebar & tinggi dari kepala IHDR PNG."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return 1600, 1200
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


class _Pengurai(HTMLParser):
    def __init__(self, gambar, lebar_cm):
        super().__init__(convert_charrefs=True)
        self.gambar = gambar or {}
        self.lebar_cm = lebar_cm
        self.badan = []            # xml blok tingkat atas
        self.media = []            # (nama berkas, bytes)
        self.para = None           # list run xml paragraf yang sedang dibuka
        self.ppr = ""
        self.gaya = []             # tumpukan format run aktif: dict
        self.tabel = None          # list baris; baris = list sel; sel = dict(xml, th, kanan)
        self.sel = None
        self.daftar = []           # tumpukan numId
        self.abaikan = 0           # di dalam <style>/<head>
        self.baris_gambar = None   # <table> tanpa kelas berisi gambar -> paragraf gambar berdampingan

    # ---------------------------------------------------------------- paragraf
    def _buka(self, ppr=""):
        if self.para is None:
            self.para, self.ppr = [], ppr

    def _tutup(self):
        if self.para is None:
            return
        xml = f"<w:p>{'<w:pPr>' + self.ppr + '</w:pPr>' if self.ppr else ''}{''.join(self.para)}</w:p>"
        if self.sel is not None:
            self.sel["xml"].append(xml)
        else:
            self.badan.append(xml)
        self.para = None

    def _rpr(self):
        r = []
        tebal = any(g.get("b") for g in self.gaya)
        miring = any(g.get("i") for g in self.gaya)
        warna = next((g["warna"] for g in reversed(self.gaya) if g.get("warna")), None)
        kecil = any(g.get("kecil") for g in self.gaya)
        mono = any(g.get("mono") for g in self.gaya)
        if mono:
            r.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>')
        if tebal:
            r.append("<w:b/>")
        if miring:
            r.append("<w:i/>")
        if warna:
            r.append(f'<w:color w:val="{warna}"/>')
        if kecil:
            r.append('<w:sz w:val="17"/><w:szCs w:val="17"/>')
        return f"<w:rPr>{''.join(r)}</w:rPr>" if r else ""

    def _teks(self, t):
        if not t:
            return
        self._buka()
        self.para.append(f'<w:r>{self._rpr()}<w:t xml:space="preserve">{escape(t)}</w:t></w:r>')

    def _gambar(self, kunci, lebar_cm):
        data = self.gambar.get(kunci)
        if not data:
            return
        n = len(self.media) + 1
        nama = f"image{n}.png"
        self.media.append((nama, data))
        w, h = ukuran_png(data)
        cx = int(lebar_cm * EMU_CM)
        cy = int(cx * h / max(1, w))
        rid = f"rIdImg{n}"
        self._buka()
        self.para.append(
            f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{n}" name="Gambar {n}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/>'
            f'</wp:cNvGraphicFramePr><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{n}" name="{nama}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
            f'</wp:inline></w:drawing></w:r>')

    # ---------------------------------------------------------------- tag
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        kelas = (a.get("class") or "").split()
        if tag in ("style", "head", "title", "script"):
            self.abaikan += 1
            return
        if self.abaikan:
            return
        if tag in ("h1", "h2", "h3"):
            self._tutup()
            self._buka(f'<w:pStyle w:val="Heading{1 if tag == "h1" else 2}"/>')
        elif tag == "p":
            self._tutup()
            self._buka('<w:pStyle w:val="Caption"/>' if "mut" in kelas and self.sel is None else "")
            self.gaya.append({"warna": next((WARNA[k] for k in kelas if k in WARNA and k != "mut"), None)})
        elif tag in ("b", "strong"):
            self.gaya.append({"b": True})
        elif tag in ("i", "em"):
            self.gaya.append({"i": True})
        elif tag == "span":
            self.gaya.append({"warna": next((WARNA[k] for k in kelas if k in WARNA), None),
                              "b": "ok" in kelas or "bad" in kelas})
        elif tag == "br":
            self._buka()
            self.para.append("<w:r><w:br/></w:r>")
        elif tag == "table":
            self._tutup()
            if "t" in kelas:
                self.tabel = []
            else:
                self.baris_gambar = []
        elif tag == "tr" and self.tabel is not None:
            self.tabel.append([])
        elif tag in ("td", "th") and self.tabel is not None and self.tabel:
            self.sel = {"xml": [], "th": tag == "th", "kanan": "n" in kelas}
            self.tabel[-1].append(self.sel)
            self.gaya.append({"b": tag == "th", "mono": "n" in kelas, "kecil": True,
                              "warna": next((WARNA[k] for k in kelas if k in WARNA), None)})
            self._buka('<w:spacing w:after="0"/>' + ('<w:jc w:val="right"/>' if "n" in kelas else ""))
        elif tag == "img":
            kunci = a.get("src", "")
            if self.baris_gambar is not None:
                self.baris_gambar.append(kunci)
            else:
                self._gambar(kunci, self.lebar_cm)
        elif tag in ("ol", "ul"):
            self._tutup()
            self.daftar.append(1 if tag == "ol" else 2)
        elif tag == "li":
            self._tutup()
            self._buka(f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{self.daftar[-1] if self.daftar else 2}"/>'
                       '</w:numPr>')

    def handle_endtag(self, tag):
        if tag in ("style", "head", "title", "script"):
            self.abaikan = max(0, self.abaikan - 1)
            return
        if self.abaikan:
            return
        if tag in ("h1", "h2", "h3", "li"):
            self._tutup()
        elif tag == "p":
            self._tutup()
            if self.gaya:
                self.gaya.pop()
        elif tag in ("b", "strong", "i", "em", "span"):
            if self.gaya:
                self.gaya.pop()
        elif tag in ("td", "th") and self.sel is not None:
            self._tutup()
            if self.gaya:
                self.gaya.pop()
            self.sel = None
        elif tag == "table":
            if self.tabel is not None:
                self._tulis_tabel()
                self.tabel = None
            elif self.baris_gambar is not None:
                g = [k for k in self.baris_gambar if self.gambar.get(k)]
                self.baris_gambar = None
                if g:
                    lebar = (self.lebar_cm - 0.4 * (len(g) - 1)) / len(g)
                    self._buka('<w:jc w:val="center"/>')
                    for i, k in enumerate(g):
                        if i:
                            self.para.append('<w:r><w:t xml:space="preserve">  </w:t></w:r>')
                        self._gambar(k, lebar)
                    self._tutup()
        elif tag in ("ol", "ul") and self.daftar:
            self.daftar.pop()

    def handle_data(self, data):
        if self.abaikan:
            return
        if self.tabel is not None and self.sel is None:
            return                      # spasi di antara sel
        t = " ".join(data.split())
        if data[:1].isspace() and t and self.para:
            t = " " + t
        if data[-1:].isspace() and t:
            t += " "
        self._teks(t)

    def _tulis_tabel(self):
        baris = [b for b in self.tabel if b]
        if not baris:
            return
        kol = max(len(b) for b in baris)
        o = ['<w:tbl><w:tblPr><w:tblStyle w:val="TabelLaporan"/><w:tblW w:w="0" w:type="auto"/>'
             '<w:tblLayout w:type="autofit"/></w:tblPr><w:tblGrid>' + '<w:gridCol/>' * kol + '</w:tblGrid>']
        for i, b in enumerate(baris):
            hdr = all(s["th"] for s in b)
            o.append("<w:tr>" + ('<w:trPr><w:tblHeader/></w:trPr>' if hdr and i == 0 else ""))
            for s in b + [{"xml": [], "th": False}] * (kol - len(b)):
                isi = "".join(s["xml"]) or "<w:p/>"
                shd = '<w:shd w:val="clear" w:color="auto" w:fill="E9ECF1"/>' if s["th"] else ""
                o.append(f"<w:tc><w:tcPr>{shd}</w:tcPr>{isi}</w:tc>")
            o.append("</w:tr>")
        o.append("</w:tbl>")
        self.badan.append("".join(o))
        self.badan.append('<w:p><w:pPr><w:spacing w:after="40"/></w:pPr></w:p>')


def simpan(html, f, gambar=None, judul="", penulis="", lebar_cm=16.0):
    """Tulis dokumen .docx dari HTML laporan. gambar: {src img: bytes PNG}."""
    u = _Pengurai(gambar, lebar_cm)
    u.feed(html)
    u.close()
    u._tutup()
    badan = "".join(u.badan)
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" '
            'w:left="1134" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr>')
    dok = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {_NS}><w:body>{badan}{sect}'
           '</w:body></w:document>')
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rIdGaya" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
            '<Relationship Id="rIdNomor" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" '
            'Target="numbering.xml"/>']
    for i, (nama, _d) in enumerate(u.media, 1):
        rels.append(f'<Relationship Id="rIdImg{i}" '
                    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                    f'Target="media/{nama}"/>')
    rels.append("</Relationships>")
    waktu = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inti = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{escape(judul)}</dc:title><dc:creator>{escape(penulis or "VirmoDock")}</dc:creator>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{waktu}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{waktu}</dcterms:modified></cp:coreProperties>')
    with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _TIPE)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", dok)
        z.writestr("word/styles.xml", _GAYA)
        z.writestr("word/numbering.xml", _NOMOR)
        z.writestr("word/_rels/document.xml.rels", "".join(rels))
        z.writestr("docProps/core.xml", inti)
        for nama, d in u.media:
            z.writestr(f"word/media/{nama}", d)
