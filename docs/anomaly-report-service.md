# Anomaly Report Service

Service ini dipakai untuk melaporkan satu temuan anomali per satu pesan WhatsApp, lalu menyimpannya ke log history agar dapat ditampilkan di dashboard.

## API

- `GET /api/anomaly-reports`
  - Mengambil riwayat laporan anomali dari log JSONL.
- `POST /api/anomaly-reports/send`
  - Membuat pesan laporan dari payload JSON, mengirimnya ke WAHA, lalu menyimpan history.

## Dashboard

Homepage dashboard menampilkan panel kecil:
- judul temuan terakhir
- status kirim
- penerima
- cuplikan isi pesan

## Log

Riwayat disimpan ke:

`/home/aseps/MCP/korespondensi-server/logs/anomaly_reports.jsonl`

## WAHA Auth Mode

Sender mendukung `WHATSAPP_API_AUTH_MODE`:

- `auto` - coba API key dulu, lalu retry tanpa key
- `key` - hanya coba dengan `X-Api-Key`
- `none` - hanya coba tanpa `X-Api-Key`

Untuk instance WAHA yang device-nya di-auth via QR, mode `none` biasanya paling bersih kalau HTTP API memang tidak meminta API key.

## Payload

Contoh payload:

```json
{
  "recipient_name": "Pak Ahmad Haidir",
  "recipient_phone": "087871393744",
  "finding_title": "No. Agenda Dispo kosong pada surat 500.5/40/SD/SUPD II",
  "finding_summary": "Satu record internal tidak membawa No. Agenda Dispo, sehingga perlu difilter sebagai anomali.",
  "record_key": "500.5/40/SD/SUPD II",
  "source_label": "SUPD II",
  "source_ref": "source_sheet=SUPD II / nomor_nd=500.5/40/SD/SUPD II",
  "impact": "Record tidak lolos validasi surat masuk PUU",
  "recommendation": "Koreksi data sumber atau bersihkan duplikat"
}
```
