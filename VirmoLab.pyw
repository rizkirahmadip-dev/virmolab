"""Titik masuk VirmoLab untuk PyInstaller (dan klik-dua-kali di Windows)."""
import multiprocessing

from virmolab.app import main

if __name__ == "__main__":
    # Wajib di build beku: tanpa ini proses pekerja ProcessPoolExecutor (penapisan farmakofor)
    # menjalankan ulang aplikasi utuh alih-alih fungsi pekerjanya.
    multiprocessing.freeze_support()
    main()
