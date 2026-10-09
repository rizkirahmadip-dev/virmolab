"""Perekam video MP4 (H.264) dari bingkai QImage, memakai Qt Multimedia (FFmpeg + encoder Media Foundation
yang sudah ikut PySide6 — tanpa paket tambahan).

Bingkai dialirkan satu per satu (tidak ditampung semua di memori): kirim() mengantre, pompa ke QVideoFrameInput
saat siap; minta_lagi() memberi tahu pemanggil kapan boleh merender bingkai berikutnya (tekanan balik).
"""
from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QMediaCaptureSession, QMediaFormat, QMediaRecorder, QVideoFrame, QVideoFrameInput

RESOLUSI = {"fhd": (1920, 1080, "Full HD 1920 × 1080"), "qhd": (2560, 1440, "2K QHD 2560 × 1440"),
            "uhd": (3840, 2160, "4K UHD 3840 × 2160"), "kotak": (1080, 1080, "Kotak 1080 × 1080 (media sosial)"),
            "tegak": (1080, 1920, "Tegak 1080 × 1920 (Reels/Story)")}


def bitrate(lebar, tinggi, fps):
    """Bitrate H.264 kualitas tinggi (≈ 0,16 bit/piksel/bingkai; 4K30 ≈ 40 Mbps, 1080p30 ≈ 10 Mbps)."""
    return int(min(120e6, max(6e6, lebar * tinggi * fps * 0.16)))


class PerekamVideo(QObject):
    selesai = Signal(str)
    galat = Signal(str)
    siap_lagi = Signal()

    def __init__(self, f, lebar, tinggi, fps, parent=None):
        super().__init__(parent)
        self.f, self.lebar, self.tinggi, self.fps = f, lebar, tinggi, fps
        self.antre = []
        self.n = 0
        self._tutup = False
        # JEBAKAN: QVideoFrameInput(format) tidak pernah 'siap' (sendVideoFrame selalu False) di Qt 6.11/Windows;
        # tanpa format, format diambil dari bingkai pertama.
        self.masuk = QVideoFrameInput()
        self.sesi = QMediaCaptureSession()
        self.sesi.setVideoFrameInput(self.masuk)
        self.rek = QMediaRecorder()
        self.sesi.setRecorder(self.rek)
        mf = QMediaFormat(QMediaFormat.FileFormat.MPEG4)
        mf.setVideoCodec(QMediaFormat.VideoCodec.H264)
        self.rek.setMediaFormat(mf)
        self.rek.setVideoResolution(lebar, tinggi)
        self.rek.setVideoFrameRate(fps)
        self.rek.setEncodingMode(QMediaRecorder.EncodingMode.AverageBitRateEncoding)
        self.rek.setVideoBitRate(bitrate(lebar, tinggi, fps))
        self.rek.setQuality(QMediaRecorder.Quality.VeryHighQuality)
        self.rek.setOutputLocation(QUrl.fromLocalFile(f))
        self.rek.errorOccurred.connect(lambda _e, t: self.galat.emit(t or "Perekam video gagal."))
        self.rek.recorderStateChanged.connect(self._status)
        self._terjadwal = False
        self.masuk.readyToSendVideoFrame.connect(self._jadwal)
        self.rek.record()

    def kirim(self, img):
        """img: QImage (diskalakan bila ukurannya lain)."""
        if img.width() != self.lebar or img.height() != self.tinggi:
            from PySide6.QtCore import Qt
            img = img.scaled(self.lebar, self.tinggi, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.antre.append(img.convertToFormat(QImage.Format_ARGB32))
        self._jadwal()

    def boleh_lagi(self):
        return len(self.antre) < 3

    def _jadwal(self):
        # lewat event loop, bukan panggilan langsung: kirim -> pompa -> siap_lagi -> kirim … berantai = stack overflow
        if not self._terjadwal:
            self._terjadwal = True
            QTimer.singleShot(0, self._pompa)

    def _pompa(self):
        self._terjadwal = False
        while self.antre:
            fr = QVideoFrame(self.antre[0])
            mulai = int(self.n * 1_000_000 / self.fps)
            fr.setStartTime(mulai)
            fr.setEndTime(int((self.n + 1) * 1_000_000 / self.fps))
            if not self.masuk.sendVideoFrame(fr):
                return                      # encoder sibuk: tunggu readyToSendVideoFrame
            self.antre.pop(0)
            self.n += 1
        if self._tutup:
            self.rek.stop()
        else:
            self.siap_lagi.emit()

    def akhiri(self):
        self._tutup = True
        if not self.antre:
            self.rek.stop()

    def batal(self):
        self.antre.clear()
        self._tutup = True
        self.rek.stop()

    def _status(self, st):
        if st == QMediaRecorder.RecorderState.StoppedState and self._tutup:
            self.selesai.emit(self.rek.actualLocation().toLocalFile() or self.f)
