# Perbaikan Upload DOCX ke Google Drive (2026-04-09)

## Gejala
- Tombol `📄 Cetak .docx` pada `/internal?q=000.4.2%2F834` gagal.
- Endpoint generate sempat mengembalikan `status: partial`.

## Akar masalah
- Backend sempat menggunakan kredensial `service_account` untuk upload Drive.
- Error berulang: `storageQuotaExceeded` (`Service Accounts do not have storage quota`) dan sebelumnya `invalid_grant`.
- Titik penting operasional: service systemd `korespondensi-server.service` membaca env dari **`/home/aseps/MCP/.env`**, bukan `korespondensi-server/.env`.

## Tindakan yang dilakukan
1. Migrasi pendekatan ke OAuth user token (`authorized_user`) untuk upload Drive.
2. Regenerasi token OAuth user via flow manual auth code (`scripts/exchange_auth_code.py`).
3. Validasi refresh token berhasil (`scratch/test_token_refresh.py` -> `Refresh success!`).
4. Validasi upload berhasil via fungsi aplikasi `upload_to_gdrive`.
5. Restart service system: `sudo systemctl restart korespondensi-server.service`.
6. Verifikasi endpoint sukses:
   - `POST /api/disposisi/generate/0327_000.4.2_834_bu_set`
   - Response: `{"status":"success","drive_url":"..."}`.

## Konfigurasi final yang dipakai
- `GDRIVE_TOKEN_PATH=/home/aseps/MCP/config/credentials/google/puubangda/token.json`
- Token file: `/home/aseps/MCP/config/credentials/google/puubangda/token.json`

## Catatan untuk troubleshooting berikutnya
- Jika muncul lagi `invalid_grant`, lakukan re-auth OAuth user dan tukar code lagi.
- Jika service tetap pakai perilaku lama setelah ubah env, pastikan file yang diedit adalah `/home/aseps/MCP/.env` lalu restart service systemd.