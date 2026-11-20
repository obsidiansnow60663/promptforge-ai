# PromptForge AI

Aplikasi Django modular untuk menyusun prompt bahasa Inggris dari instruksi pengguna, meninjau hasil, mengeksekusi prompt melalui OpenAI, Anthropic atau Google Gemini, serta mengadaptasi hasil ke Bahasa Indonesia. Menggunakan PostgreSQL, HTMX, Alpine.js dan Tailwind CSS; tidak menggunakan Docker.

## Persiapan lokal

Diperlukan Python 3.10+, PostgreSQL dan koneksi internet. Siapkan PostgreSQL, misalnya melalui `psql` sebagai administrator:

```sql
CREATE USER promptforge WITH PASSWORD 'ganti-password';
CREATE DATABASE promptforge OWNER promptforge;
```

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`: atur password PostgreSQL, `DJANGO_SECRET_KEY` yang acak (buat dengan `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`), serta setidaknya satu kunci `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` atau `GOOGLE_API_KEY`. Kunci disimpan di server dalam environment, bukan di browser; jangan commit `.env`. Model pada UI adalah contoh, sesuaikan dengan akses dan model terbaru provider.

```bash
python manage.py migrate
python manage.py runserver
```

Buka http://127.0.0.1:8000/, daftar akun, lalu gunakan ruang kerja. `GET /health/` hanya memeriksa liveness, bukan koneksi PostgreSQL. Eksekusi dan perbandingan mengirim data ke provider dan dapat menimbulkan biaya. Setiap pengguna hanya dapat mengakses riwayatnya sendiri. Penghapusan akun akan menghapus riwayatnya.

## Alur kualitas

Generator menganalisis instruksi, menyusun prompt, lalu melakukan tinjauan. Jika tinjauan menemukan kekurangan atau asumsi, maksimal dua revisi dilakukan. Skor berbobot adalah penilaian model yang bersifat eksperimental, bukan jaminan kualitas; kegagalan kritis tetap menghasilkan peringatan dan menghentikan eksekusi otomatis. Hasil eksekusi dapat diadaptasi ke Bahasa Indonesia dan ditinjau secara terpisah. Keduanya memakai model yang dipilih, sehingga bukan peninjauan independen dan perlu verifikasi manusia.

## Pengujian

```bash
PROMPTFORGE_TEST_SQLITE=1 python manage.py test
python manage.py check
```

SQLite hanya untuk menjalankan tes terisolasi; aplikasi menggunakan PostgreSQL. Integrasi langsung memerlukan database dan API key yang valid.

## Batasan saat ini

Permintaan berjalan sinkron; belum ada antrean, pembatalan, idempotensi, rate limiting, manajemen kunci per pengguna, versioning, API publik, dashboard benchmark, dataset evaluasi 100 contoh, atau pengukuran biaya. Perbandingan memproses model berurutan dan penghitungan penggunaan hanya mencakup respons eksekusi awal, tidak termasuk tahap generasi/review/adaptasi. Pengumpulan feedback belum digunakan untuk melatih atau mengubah model. Jangan menganggap skor AI sebagai bukti validasi benchmark atau jaminan akurasi. Tailwind Play CDN hanya untuk pengembangan; build CSS sendiri untuk produksi. Sebelum deployment, tambahkan hardening dan jalankan `python manage.py check --deploy` dengan pengaturan produksi yang sesuai.
