# 📄 PDF Compressor

Kompresi PDF cepat, aman, dan sepenuhnya berjalan di komputer Anda.

Dengan tampilan modern dan alur kerja sederhana:

1. Pilih PDF
2. Pilih tingkat kompresi
3. Klik **Kompres PDF**

File asli tidak akan diubah. Hasil kompresi otomatis dibuat sebagai file baru di folder yang sama.

---

## ✨ Fitur Utama

- 🔒 Pemrosesan 100% lokal, tanpa upload ke internet
- 📄 Mendukung drag & drop file PDF
- ⚡ Kompresi cepat dengan 3 tingkat kualitas
- 🛡️ File asli tetap aman dan tidak ditimpa
- 📊 Menampilkan ukuran sebelum dan sesudah kompresi
- 📁 Langsung buka folder hasil kompresi
- ✅ Otomatis membuat nama file baru untuk menghindari overwrite

---

## 🖼️ Tampilan Aplikasi

docs/images/app-main-window.png

---

## 🚀 Cara Menggunakan

1. Jalankan `PDF Compressor.exe`
2. Seret file PDF ke aplikasi atau klik **Pilih PDF**
3. Pilih tingkat kompresi
4. Klik **Kompres PDF**
5. File hasil akan muncul di folder yang sama dengan file asli

Contoh:

```text
Laporan.pdf
↓
Laporan_Kompres_L2.pdf
```

---

## 🎯 Tingkat Kompresi

| Mode | Cocok Untuk | Pengaturan |
|--------|--------|--------|
| Kualitas Tinggi | Dokumen penting & cetak | 200 DPI • JPEG 85 |
| Seimbang (Rekomendasi) | Penggunaan sehari-hari | 150 DPI • JPEG 75 |
| Ukuran Kecil | Prioritas ukuran file | 110 DPI • JPEG 65 |

---

## ℹ️ Penting

Untuk mendapatkan ukuran file yang lebih kecil, setiap halaman PDF akan dikonversi menjadi gambar.

Akibatnya:

- Teks tidak dapat dicari (search)
- Teks tidak dapat disalin atau diedit
- Hyperlink, bookmark, dan formulir tidak dipertahankan
- PDF yang sudah sangat optimal mungkin tidak berkurang ukurannya
- PDF terenkripsi atau rusak belum didukung

---

## 💻 Persyaratan Sistem

- Windows 10 / Windows 11 64-bit
- Tidak memerlukan Python
- Tidak memerlukan Ghostscript
- Tidak memerlukan hak Administrator
- Tidak perlu instalasi tambahan

Cukup jalankan:

```text
PDF Compressor.exe
```

---

## 🛠️ Build Dari Source

Build aplikasi:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

Build offline:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1 -Offline
```

---

## 📜 Lisensi

Aplikasi ini menggunakan PyMuPDF.

Daftar lisensi pihak ketiga tersedia pada:

`THIRD_PARTY_NOTICES.md`
