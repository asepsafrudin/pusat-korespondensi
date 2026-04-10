# POSISI Knowledge Terms

Dokumentasi bridge read-only untuk daftar token unik dari kolom `POSISI`.

## Endpoint

`GET /api/knowledge/posisi/terms`

### Query Params

- `limit` - batas jumlah token unik yang dikembalikan, default `500`, maksimum `2000`
- `q` - filter teks sederhana untuk mempersempit token

### Response

Setiap item berisi:

- `term` - token unik hasil normalisasi
- `count` - frekuensi kemunculan token
- `sheets` - daftar sheet sumber tempat token muncul
- `examples` - beberapa contoh raw `POSISI`

## Use Case

- Menyusun kamus istilah dari data `POSISI`
- Menentukan token mana yang perlu definisi manual
- Melihat frekuensi istilah lintas sheet tanpa koneksi DB langsung

## Catatan

- Endpoint ini hanya membaca data.
- Token diekstrak secara heuristik dari string raw `POSISI`.
- Hasilnya cocok sebagai daftar awal kamus, lalu bisa diperkaya manual.
