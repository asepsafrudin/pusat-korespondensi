import json
import re
import os

# Load referensi utama (hasil konversi sebelumnya)
REFERENSI_FILE = 'docs/kodefikasi_arsip_index.json'
if os.path.exists(REFERENSI_FILE):
    with open(REFERENSI_FILE, 'r') as f:
        data_referensi = json.load(f)
        # File ini berbentuk dictionary {kode: {description, level, ...}}
        # Kita perlu konversi ke format yang sesuai untuk lookup
        kode_lookup = {}
        for kode, info in data_referensi.items():
            kode_lookup[kode] = {
                'kode': kode,
                'uraian': info.get('description', ''),
                'level': info.get('level', 0),
                'hierarki': []  # Akan diisi jika diperlukan
            }
else:
    kode_lookup = {}
    print(f"Peringatan: File {REFERENSI_FILE} tidak ditemukan. Validasi kode hanya bersifat dasar.")

# --- MODEL MAPPING (JEMBATAN) ---
# Diambil dari logika Google Apps Script Anda
# DIPERBARUI: TU sekarang merujuk ke Bagian Umum (000.2.2) karena TU adalah sub-bagian dari BU
CONFIG_MAP = {
    "SD.I":   {"kode_utama": "600.9",  "nama_bidang": "Pekerjaan Umum", "desc": "Bidang Bina Pemerintahan Kelurahan & Desa"},
    "SD.II":  {"kode_utama": "600.10", "nama_bidang": "Perumahan dan Kawasan Pemukiman", "desc": "Bidang Bina Pemerintahan Kecamatan"},
    "SD.III": {"kode_utama": "500.5",  "nama_bidang": "Kelautan dan Perikanan", "desc": "Bidang Perikanan Tangkap"},
    "SD.IV":  {"kode_utama": "500.7",  "nama_bidang": "Perhubungan", "desc": "Bidang Lalu Lintas & Angkutan Jalan"},
    "SD.V":   {"kode_utama": "500.8",  "nama_bidang": "Komunikasi dan Informatika", "desc": "Bidang Angkutan Multimoda"},
    "SD.VI":  {"kode_utama": "700.1",  "nama_bidang": "Kepemudaan dan Olahraga", "desc": "Bidang Kepemudaan & Olahraga"},
    # UPDATE PENTING: TU dipetakan ke Bagian Umum (000.2.2) karena TU adalah sub-bagian dari BU
    "TU":     {"kode_utama": "000.2.2", "nama_bidang": "Bagian Umum", "desc": "Sub Bagian Tata Usaha di bawah Bagian Umum"},
    "BU":     {"kode_utama": "000.2.2", "nama_bidang": "Bagian Umum", "desc": "Bagian Umum"},
    "SET":    {"kode_utama": "000.2",   "nama_bidang": "Sekretariat", "desc": "Sekretariat"},
    "PRC":    {"kode_utama": "000.3",   "nama_bidang": "Perencanaan", "desc": "Perencanaan"},
    "KEU":    {"kode_utama": "900.1",   "nama_bidang": "Keuangan", "desc": "Keuangan"},
    "PUU":    {"kode_utama": "100.4",   "nama_bidang": "Pemerintahan Umum", "desc": "Pemerintahan Umum"}
}

def normalisasi_kode(kode_str):
    """Normalisasi format kode: ganti '-' dengan '.', hapus spasi."""
    if not kode_str:
        return ""
    # Hapus spasi
    kode_str = kode_str.strip()
    # Ganti pemisah '-' menjadi '.' untuk konsistensi (menangani kasus 500-8 -> 500.8)
    # Tapi hati-hati dengan nomor surat yang pakai '-', jadi hanya di bagian depan sebelum '/'
    parts = kode_str.split('/')
    if parts:
        # Normalisasi bagian kode saja (bagian pertama)
        parts[0] = parts[0].replace('-', '.').replace(' ', '')
        # Gabungkan kembali jika ada lebih dari 1 part (untuk jaga-jaga struktur)
        return '/'.join(parts)
    return kode_str

def ekstrak_unit_kerja(teks_nomor_nd):
    """
    Mengekstrak kode unit kerja (SD.I, SD.II, TU, dll) dari string NOMOR ND.
    Pola umum: KODE/NOMOR/UNIT/TAHUN atau KODE/NOMOR/UNIT.SUB/TAHUN
    """
    if not teks_nomor_nd:
        return None, None
    
    parts = teks_nomor_nd.split('/')
    unit_terdeteksi = None
    kode_mapping = None
    nama_bidang = None
    
    # Cari pola unit kerja di setiap bagian
    for part in parts:
        part_clean = part.strip().upper()
        # Cek apakah bagian ini ada di kunci CONFIG_MAP
        # Kita perlu cek variasi penulisan, misal "SD.IV" vs "SD IV"
        
        # Normalisasi part untuk pencocokan (hapus titik, spasi)
        part_normalized = re.sub(r'[.\s]', '', part_clean)
        
        for key in CONFIG_MAP:
            key_normalized = re.sub(r'[.\s]', '', key)
            if part_normalized == key_normalized or part_clean.startswith(key.replace('.', '')):
                unit_terdeteksi = key
                kode_mapping = CONFIG_MAP[key]['kode_utama']
                nama_bidang = CONFIG_MAP[key]['nama_bidang']
                break
        
        if unit_terdeteksi:
            break
            
    # Kasus khusus: "TU.SUPD II" -> cari "TU"
    if not unit_terdeteksi and "TU" in parts[-1].upper():
         unit_terdeteksi = "TU"
         kode_mapping = CONFIG_MAP["TU"]["kode_utama"]
         nama_bidang = CONFIG_MAP["TU"]["nama_bidang"]

    return unit_terdeteksi, kode_mapping, nama_bidang

def parse_dengan_mapping(nomor_nd):
    """
    Fungsi utama parsing yang menggabungkan validasi kode arsip 
    dengan mapping unit kerja.
    """
    if not nomor_nd:
        return {"error": "Nomor ND kosong"}

    original_input = nomor_nd
    nomor_nd_normal = normalisasi_kode(nomor_nd)
    
    # Pisahkan komponen
    parts = nomor_nd_normal.split('/')
    kodeklas = parts[0].strip() if parts else ""
    
    # 1. Validasi terhadap Referensi Utama (Permendagri)
    status_validasi = "UNKNOWN"
    deskripsi = "Tidak ditemukan dalam referensi Permendagri 83/2022"
    level = 0
    hierarki = []
    
    # Coba match exact
    if kodeklas in kode_lookup:
        item = kode_lookup[kodeklas]
        status_validasi = "EXACT_MATCH"
        deskripsi = item.get('uraian', 'Tanpa Deskripsi')
        level = item.get('level', 0)
        hierarki = item.get('hierarki', [])
    else:
        # Coba match parent (fallback)
        parts_kode = kodeklas.split('.')
        for i in range(len(parts_kode)-1, 0, -1):
            parent_code = '.'.join(parts_kode[:i])
            if parent_code in kode_lookup:
                item = kode_lookup[parent_code]
                status_validasi = "FALLBACK_PARENT"
                deskripsi = f"{item.get('uraian', '')} (Kode spesifik {kodeklas} tidak terdaftar, menggunakan induk {parent_code})"
                level = item.get('level', 0)
                hierarki = item.get('hierarki', [])
                break

    # 2. Deteksi Unit Kerja & Mapping Jembatan
    unit_kerja, kode_mapping_unit, nama_bidang = ekstrak_unit_kerja(nomor_nd)
    
    # 3. Validasi Silang (Cross-Validation)
    konsistensi = "OK"
    catatan = []
    
    if unit_kerja and kodeklas:
        # Ambil 3 digit pertama atau 4 digit pertama dari kode klasifikasi surat
        # Karena mapping kita menggunakan kode utama (e.g., 600.9)
        prefix_kode_surat = '.'.join(kodeklas.split('.')[:2]) if '.' in kodeklas else kodeklas.split('.')[0]
        
        # Normalisasi kode mapping untuk perbandingan
        if kode_mapping_unit:
            # Cek apakah prefix kode surat sesuai dengan mapping unit
            # Contoh: Surat 600.9 harusnya SD.I
            if not prefix_kode_surat.startswith(kode_mapping_unit.split('.')[0]):
                # Logika longgar: cek apakah kode surat ADA DI BAWAH naungan kode mapping
                # Misal mapping 600.9, surat 600.9.1 -> OK
                konsistensi = "WARNING"
                catatan.append(f"Potensi ketidaksesuaian: Unit {unit_kerja} ({nama_bidang}) biasanya menggunakan kode {kode_mapping_unit}, namun surat menggunakan kode {kodeklas}.")
            else:
                konsistensi = "CONSISTENT"
                catatan.append(f"Kode {kodeklas} konsisten dengan unit {unit_kerja} ({nama_bidang}).")

    return {
        "input_asli": original_input,
        "input_normalisasi": nomor_nd_normal,
        "kode_klasifikasi": kodeklas,
        "validasi_referensi": {
            "status": status_validasi,
            "deskripsi": deskripsi,
            "level": level,
            "hierarki": hierarki
        },
        "deteksi_unit": {
            "unit_kerja": unit_kerja,
            "nama_bidang": nama_bidang,
            "kode_mapping": kode_mapping_unit
        },
        "analisis_konsistensi": {
            "status": konsistensi,
            "catatan": catatan
        }
    }

# --- TESTING DENGAN DATA BARU (LENGKAP 34 ENTRI) ---
data_uji = [
    "500-8/261-03/SD.V/2025",
    "500.7/260-08/SD.IV/2025",
    "500.7/640/SD.IV",
    "600.10/002.11/SD II/2026",
    "500.8/003.01/SD.V/2026",
    "003.05/UN/TU.SUPD. II/2026",
    "500.7/261.04/SD IV/2025",
    "004-06/SD.II/TU.SUPD.II/I/2026",
    "500.7/004-05/SD.IV/2026",
    "600.9/005.01/SD I/2026",
    "600.9/005-05",
    "600.9/006.02/SD.I/2026",
    "600.10/006.01/SD.II/2026",
    "500.8/007.05/SD V/2026",
    "600.10 /009-04 / SD. II / 2026",
    "500.7/010.01/SD.IV/2026",
    "600.10/010-05/SD.II/2026",
    "500.5/010-08/SD.III/2026",
    "500.8/010-09/SD.V/2026",
    "500.8/010-04/SD.V/2026",
    "010-07/UM/TU-SUPD.II/2026",
    "600.10/011.02/SD.II/2026",
    "500.8/011-04/SD V/2026",
    "500.7/011-03/SD.IV/2026",
    "600.9/013-05/SD.I/2026",
    "500.7/015.01/SD.IV/2026",
    "500.7/015.02/SD.IV/2026",
    "500.8/016.2/SD.V/2026",
    "500.7/016.05/SD.IV/2026",
    "016.04/UM/TU.SUPD II/2026",
    "600.10/017.07/SD.II/2026",
    "500.8/018.03/SD.V/2026",
    "500.5/018.02/SD.III/2026",
    "500.8/019-05/SD.V/2026"
]

print(f"{'='*20} HASIL PARSING DENGAN MAPPING JEMBATAN {'='*20}\n")

hasil_lengkap = []

for nomor in data_uji:
    result = parse_dengan_mapping(nomor)
    hasil_lengkap.append(result)
    
    print(f"Input: {result['input_asli']}")
    print(f"  -> Kode: {result['kode_klasifikasi']} | Status: {result['validasi_referensi']['status']}")
    print(f"  -> Deskripsi: {result['validasi_referensi']['deskripsi'][:60]}...")
    print(f"  -> Unit Terdeteksi: {result['deteksi_unit']['unit_kerja']} ({result['deteksi_unit']['nama_bidang']})")
    print(f"  -> Konsistensi: {result['analisis_konsistensi']['status']}")
    if result['analisis_konsistensi']['catatan']:
        print(f"     Catatan: {result['analisis_konsistensi']['catatan'][0]}")
    print("-" * 80)

# Simpan ke file
output_file = "docs/hasil_parsing_dengan_mapping.json"
with open(output_file, 'w') as f:
    json.dump(hasil_lengkap, f, indent=2)

print(f"\n✅ Hasil lengkap disimpan ke: {output_file}")
print(f"Total data diproses: {len(hasil_lengkap)}")
