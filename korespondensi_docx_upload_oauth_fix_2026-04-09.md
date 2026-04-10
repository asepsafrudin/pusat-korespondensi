# Korespondensi Server - Perbaikan Upload DOCX ke Google Drive

Tanggal: 2026-04-09

## Ringkasan Masalah
- Tombol `📄 Cetak .docx` pada halaman internal gagal bekerja untuk kasus `q=000.4.2/834`.
- API sempat mengembalikan `status: partial` karena upload ke Google Drive gagal.

## Akar Penyebab
- Upload berjalan memakai kredensial `service_account`.
- Google Drive menolak upload dengan error `storageQuotaExceeded`:
  `Service Accounts do not have storage quota`.
- Di fase sebelumnya juga muncul `invalid_grant` pada token OAuth lama (revoked/expired).

## Tindakan Perbaikan
1. Migrasi jalur upload ke OAuth user token (`authorized_user`).
2. Perbarui path token aktif ke:
   `/home/aseps/MCP/config/credentials/google/puubangda/token.json`
3. Regenerasi token OAuth via flow auth code.
4. Verifikasi refresh token berhasil.
5. Restart service `korespondensi-server.service`.

## Validasi Hasil
- Endpoint uji:
  `POST /api/disposisi/generate/0327_000.4.2_834_bu_set`
- Hasil akhir: `{"status":"success","drive_url":"..."}`
- Artinya tombol `.docx` sudah kembali berfungsi normal.

## Catatan Operasional Penting
- Service systemd `korespondensi-server.service` membaca env dari:
  `/home/aseps/MCP/.env`
  (bukan `korespondensi-server/.env`).
- Jika gejala terulang dengan `invalid_grant`, lakukan re-auth OAuth user lagi.
