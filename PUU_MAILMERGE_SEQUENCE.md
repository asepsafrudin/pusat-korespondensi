# PUU Mailmerge Sequence

Dokumen ini menjelaskan sumber data dan cara cek kesehatan field yang dipakai mailmerge PUU.

## Sequence `agenda_puu`

`agenda_puu` dibentuk dari urutan kronologis surat PUU:

- diurutkan berdasarkan `tanggal_surat`
- lalu `id` sebagai tie-breaker
- nomor urut diformat `LPAD(..., 3, '0')`
- diberi suffix `-I`

Contoh hasil: `062-I`, `072-I`, `074-I`

## Sumber Data

- `agenda_puu` resmi dibentuk di tabel `lembar_disposisi`
- `surat_masuk_puu_internal` ikut diisi lewat sinkronisasi agar mailmerge native bisa membacanya
- `no_agenda_dispo` dan `tanggal_diterima_puu` dibaca langsung dari `surat_masuk_puu_internal`

## Audit Script

Gunakan script ini untuk cek field penting sebelum generate DOCX:

```bash
python3 scripts/report_puu_mailmerge_health.py --limit 20
python3 scripts/report_puu_mailmerge_health.py --unique-id 0327_000.4.2_834_bu_set
```

Script akan menandai baris yang masih kurang pada:

- `no_agenda_dispo`
- `agenda_puu`
- `tanggal_diterima_puu`

## POSISI Mapping Workflow

Jika yang ingin dicek adalah logika pembacaan kolom `POSISI`, gunakan:

```bash
python3 scripts/report_puu_posisi_mapping.py --limit 20
python3 scripts/report_puu_posisi_mapping.py --unique-id 0327_000.4.2_834_bu_set
python3 scripts/report_puu_posisi_mapping.py --json-out storage/admin_data/korespondensi/puu_posisi_mapping_audit.json
```

Script ini membaca helper aktif di `mcp-unified/integrations/korespondensi/utils.py` dan merangkum:

- timeline event
- status terakhir
- tanggal diterima PUU
- apakah row lolos sebagai surat masuk PUU

Workflow ETL utama juga menjalankan audit ini otomatis setelah sync selesai dan menulis hasil JSON ke:

`storage/admin_data/korespondensi/puu_posisi_mapping_audit.json`

Jika audit menemukan anomali, ETL tetap lanjut karena langkah ini bersifat observasi, bukan blocking.

## Mapping POSISI di UI

Halaman `internal` sekarang menampilkan label hasil mapping sebagai teks utama timeline.

- Label dibentuk oleh helper `src/services/posisi_mapping.py`
- Teks `POSISI` asli tetap ditampilkan sebagai detail pendukung
- Tujuannya supaya pengguna melihat versi yang lebih mudah dibaca, tanpa kehilangan konteks mentah untuk verifikasi
