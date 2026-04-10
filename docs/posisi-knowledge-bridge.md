# POSISI Knowledge Bridge

Dokumentasi bridge read-only untuk inspeksi data unik pada kolom `POSISI`.

## Endpoint

`GET /api/knowledge/posisi/unique`

### Query Params

- `limit` - batas jumlah nilai unik yang dikembalikan, default `200`, maksimum efektif `1000`
- `q` - filter teks sederhana untuk mempersempit nilai `POSISI`

### Response

```json
{
  "status": "success",
  "count": 1,
  "limit": 200,
  "query": "",
  "data": [
    {
      "posisi_raw": "SES 16/3 KOREKSI 16/3 SES 6/4 PUU, BU 6/4",
      "count": 1,
      "timeline": [
        {
          "unit": "SES",
          "date": "16/3",
          "action": "POSITION_CHECK",
          "notes": "",
          "label": "SES 16 Maret - Posisi diterima"
        }
      ]
    }
  ]
}
```

## Use Case

- Audit nilai unik `POSISI` tanpa akses DB langsung
- Meninjau hasil parsing timeline untuk agent IDE sandbox
- Menjadi bridge minimal sebelum kita memikirkan proxy/database gateway yang lebih besar

## Catatan

- Endpoint ini hanya membaca data.
- Data mentah tetap tersedia di `posisi_raw` agar mudah diverifikasi.
- Hasil timeline memakai helper lokal `build_posisi_timeline_view(...)`.
