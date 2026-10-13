"""Prediksi konformal split (inductive conformal prediction) untuk QSAR.

Regresi  : interval prediksi y_hat +/- q, dengan q = kuantil (1 - alfa) dari galat mutlak pada set kalibrasi.
Klasifikasi: himpunan label yang skor kesesuaiannya melewati ambang kalibrasi (bisa kosong atau berisi > 1 label).

Jaminan cakupan berlaku bila data kalibrasi dan uji dapat dipertukarkan (exchangeable) dan set kalibrasi tidak
dipakai melatih model. Implementasi mandiri, tanpa paket tambahan.
"""
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


class KonformalRegresi:
    """Interval prediksi bertaraf 1 - alfa (bawaan 90 %) dari galat set kalibrasi."""

    def __init__(self, alfa: float = 0.1, ternormalisasi: bool = False):
        self.alfa = float(alfa)
        self.ternormalisasi = bool(ternormalisasi)   # True: skala galat dengan sebaran prediksi antar-pohon
        self.q: Optional[float] = None
        self.n_kalibrasi = 0

    def kalibrasi(self, y_benar: Sequence[float], y_prediksi: Sequence[float],
                  sebaran: Optional[Sequence[float]] = None) -> float:
        y_benar, y_prediksi = np.asarray(y_benar, float), np.asarray(y_prediksi, float)
        skor = np.abs(y_benar - y_prediksi)
        if self.ternormalisasi and sebaran is not None:
            skor = skor / (np.asarray(sebaran, float) + 1e-6)
        n = len(skor)
        if n < 10:
            raise ValueError(f"Set kalibrasi terlalu kecil untuk prediksi konformal ({n} senyawa, minimal 10).")
        # kuantil konformal: ceil((n+1)(1-alfa))/n, dibatasi <= 1 agar tetap sah untuk n kecil
        k = min(1.0, np.ceil((n + 1) * (1 - self.alfa)) / n)
        self.q = float(np.quantile(skor, k, method="higher"))
        self.n_kalibrasi = n
        return self.q

    def interval(self, y_prediksi: Sequence[float], sebaran: Optional[Sequence[float]] = None) -> np.ndarray:
        """[[bawah, atas], ...] untuk tiap prediksi."""
        if self.q is None:
            raise RuntimeError("Konformal belum dikalibrasi.")
        y = np.asarray(y_prediksi, float)
        lebar = self.q * (np.asarray(sebaran, float) + 1e-6) if (self.ternormalisasi and sebaran is not None) else self.q
        return np.column_stack([y - lebar, y + lebar])

    def cakupan(self, y_benar: Sequence[float], y_prediksi: Sequence[float],
                sebaran: Optional[Sequence[float]] = None) -> float:
        """Bagian senyawa yang nilai sebenarnya jatuh di dalam interval (uji empiris pada set uji)."""
        iv = self.interval(y_prediksi, sebaran)
        y = np.asarray(y_benar, float)
        return float(np.mean((y >= iv[:, 0]) & (y <= iv[:, 1])))

    def ke_dict(self) -> Dict[str, Any]:
        return {"alfa": self.alfa, "ternormalisasi": self.ternormalisasi, "q": self.q, "n_kalibrasi": self.n_kalibrasi}

    @classmethod
    def dari_dict(cls, d: Dict[str, Any]) -> "KonformalRegresi":
        k = cls(d.get("alfa", 0.1), d.get("ternormalisasi", False))
        k.q, k.n_kalibrasi = d.get("q"), d.get("n_kalibrasi", 0)
        return k


class KonformalKlasifikasi:
    """Himpunan prediksi bertaraf 1 - alfa dari skor kesesuaian 1 - P(kelas benar) pada set kalibrasi."""

    def __init__(self, alfa: float = 0.1):
        self.alfa = float(alfa)
        self.q: Optional[float] = None
        self.n_kalibrasi = 0

    def kalibrasi(self, y_benar: Sequence[int], peluang: np.ndarray) -> float:
        peluang = np.asarray(peluang, float)
        y = np.asarray(y_benar, int)
        skor = 1.0 - peluang[np.arange(len(y)), y]
        n = len(skor)
        if n < 10:
            raise ValueError(f"Set kalibrasi terlalu kecil untuk prediksi konformal ({n} senyawa, minimal 10).")
        k = min(1.0, np.ceil((n + 1) * (1 - self.alfa)) / n)
        self.q = float(np.quantile(skor, k, method="higher"))
        self.n_kalibrasi = n
        return self.q

    def himpunan(self, peluang: np.ndarray) -> List[List[int]]:
        if self.q is None:
            raise RuntimeError("Konformal belum dikalibrasi.")
        peluang = np.asarray(peluang, float)
        return [[int(k) for k in range(peluang.shape[1]) if 1.0 - p[k] <= self.q] for p in peluang]

    def cakupan(self, y_benar: Sequence[int], peluang: np.ndarray) -> float:
        hs = self.himpunan(peluang)
        return float(np.mean([int(y) in h for y, h in zip(y_benar, hs)]))

    def ke_dict(self) -> Dict[str, Any]:
        return {"alfa": self.alfa, "q": self.q, "n_kalibrasi": self.n_kalibrasi}

    @classmethod
    def dari_dict(cls, d: Dict[str, Any]) -> "KonformalKlasifikasi":
        k = cls(d.get("alfa", 0.1))
        k.q, k.n_kalibrasi = d.get("q"), d.get("n_kalibrasi", 0)
        return k
