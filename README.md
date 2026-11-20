# PromptForge AI

Fondasi modular monolith untuk platform rekayasa prompt Bahasa Indonesia. Fase ini menyediakan proyek Django, halaman awal, konfigurasi PostgreSQL, dan endpoint liveness. Belum ada integrasi LLM, generator prompt, akun pengguna aplikasi, atau pemrosesan background.

## Persyaratan

Python 3.10+ (disarankan 3.12), PostgreSQL yang berjalan secara lokal, dan akses internet untuk CDN UI. Tidak menggunakan Docker.

## Menjalankan lokal

1. Buat role dan database PostgreSQL, misalnya melalui `psql` sebagai administrator:

   ```sql
   CREATE USER promptforge WITH PASSWORD 'ganti-password';
   CREATE DATABASE promptforge OWNER promptforge;
   ```

2. Dari direktori proyek:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. Isi `.env` dengan kredensial PostgreSQL yang sesuai dan secret acak. Contoh membuat secret: `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`.
4. Jalankan migrasi Django dan server:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

Buka http://127.0.0.1:8000/. `GET /health/` adalah pemeriksaan liveness proses dan tidak memeriksa koneksi database. Django admin tersedia di `/admin/`; buat akun admin dengan `python manage.py createsuperuser` bila diperlukan.

## Pengujian

```bash
PROMPTFORGE_TEST_SQLITE=1 python manage.py test
python manage.py check
```

SQLite hanya digunakan sebagai alternatif untuk pengujian fondasi; aplikasi dikonfigurasi menggunakan PostgreSQL. Uji koneksi database nyata dengan menjalankan migrasi terhadap PostgreSQL lokal.

## Arsitektur dan tahapan

Django menyajikan HTML dan endpoint dalam satu aplikasi. HTMX dan Alpine.js dimuat untuk interaksi di fase berikutnya; Tailwind Play CDN dipakai untuk kemudahan pengembangan awal dan harus diganti dengan CSS hasil build sebelum produksi. Aset CDN memerlukan koneksi internet. Selanjutnya: skema domain dan abstraksi provider, pipeline Prompt Intelligence dan generate-only, eksekusi multi-provider, adaptasi output, evaluasi, lalu hardening. Tidak ada pemrosesan LLM pada fase ini.

Konfigurasi default hanya untuk pengembangan. Sebelum deployment, gunakan secret yang kuat, `DEBUG=false`, hosts dan HTTPS yang tepat, server WSGI/ASGI produksi, pengaturan cookie aman, dan jalankan `python manage.py check --deploy`. Jangan commit `.env` atau kredensial.
