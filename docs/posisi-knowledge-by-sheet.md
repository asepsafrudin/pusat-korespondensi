# POSISI Knowledge Bridge per Sheet

Dokumentasi bridge read-only untuk mapping nilai unik `POSISI` yang
dikelompokkan berdasarkan sumber sheet di database.

## Endpoint

`GET /api/knowledge/posisi/by-sheet`

### Query Params

- `limit_per_sheet` - batas jumlah nilai unik per sheet, default `100`, maksimum `1000`
- `q` - filter teks sederhana untuk mempersempit nilai `POSISI`

### Response

Setiap item berisi:

- `source_spreadsheet_id`
- `source_sheet_name`
- `count`
- `data`

Setiap item di `data` berisi:

- `posisi_raw`
- `count`
- `timeline`

## Use Case

- Bandingkan pola `POSISI` antar sheet sumber
- Audit nilai unik berdasarkan asal data
- Bantu agent sandbox yang tidak bisa mengakses PostgreSQL langsung

## Catatan

- Endpoint ini read-only.
- Timeline masih memakai helper lokal `build_posisi_timeline_view(...)`.
- Jika ada pattern yang sama muncul di beberapa sheet, masing-masing sheet akan
  dilaporkan terpisah.
