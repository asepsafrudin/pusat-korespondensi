import json
import re
import os

# Load data referensi yang sudah dibuat sebelumnya
referensi_path = 'docs/kodefikasi_arsip_index.json'
if not os.path.exists(referensi_path):
    raise FileNotFoundError(f"File referensi tidak ditemukan di {referensi_path}. Jalankan proses konversi CSV dulu.")

with open(referensi_path, 'r', encoding='utf-8') as f:
    # Struktur index: dictionary langsung { "kode": {detail} }
    data_referensi = json.load(f)

# Data sudah dalam format dictionary, siap digunakan sebagai lookup table
lookup_table = data_referensi

def normalize_code(code_str):
    """
    Normalisasi kode:
    - Hapus spasi
    - Ganti pemisah '-' dengan '.' agar sesuai standar referensi
    - Pastikan format angka konsisten
    """
    if not code_str:
        return None
    # Hapus spasi
    clean = code_str.strip()
    # Ganti '-' dengan '.' untuk standarisasi awal (karena data baru pakai '-')
    # Tapi hati-hati, jangan sampai mengganti '-' pada nomor surat nanti. 
    # Di sini kita hanya fokus di bagian KODE (sebelum '/')
    return clean.replace('-', '.').replace(' ', '')

def parse_nomor_surat(raw_string):
    """
    Parser canggih untuk format campuran:
    Contoh: '500-8/261-03/SD.V/2025' atau '600.10 /009-04 / SD. II / 2026'
    """
    # 1. Bersihkan spasi berlebih di sekitar '/'
    cleaned = re.sub(r'\s*/\s*', '/', raw_string.strip())
    
    # Pisahkan berdasarkan '/'
    parts = cleaned.split('/')
    
    if len(parts) < 2:
        return None # Format tidak valid
    
    raw_kode = parts[0].strip()
    
    # Normalisasi kode khusus untuk pencocokan
    normalized_kode = normalize_code(raw_kode)
    
    # Ekstrak bagian lain (Nomor, Unit, Tahun) - sisa parts
    nomor_surat = parts[1].strip() if len(parts) > 1 else ""
    unit = parts[2].strip() if len(parts) > 2 else ""
    tahun = parts[3].strip() if len(parts) > 3 else ""
    
    return {
        "raw_input": raw_string,
        "raw_kode": raw_kode,
        "normalized_kode": normalized_kode,
        "nomor_surat": nomor_surat,
        "unit": unit,
        "tahun": tahun
    }

def cari_referensi(kode_normalisasi):
    """
    Mencari kode di referensi dengan strategi fallback:
    1. Exact match
    2. Match per level (hapus sub-kode terakhir bertahap)
    """
    if not kode_normalisasi:
        return None, "INVALID_CODE", None
    
    # 1. Coba Exact Match
    if kode_normalisasi in lookup_table:
        return lookup_table[kode_normalisasi], "EXACT_MATCH", kode_normalisasi
    
    # 2. Fallback: Pecah kode dan coba cari parent terdekat
    parts = kode_normalisasi.split('.')
    current_code = ""
    best_match = None
    matched_code = None
    
    for i, part in enumerate(parts):
        if i == 0:
            current_code = part
        else:
            current_code += "." + part
        
        # Cek apakah kode sementara ini ada di referensi
        if current_code in lookup_table:
            best_match = lookup_table[current_code]
            matched_code = current_code
    
    if best_match:
        return best_match, "FALLBACK_PARENT", matched_code
    
    return None, "UNKNOWN_CODE", None

# Data Input Baru
data_baru = [
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

hasil_parsing = []
statistik = {"EXACT_MATCH": 0, "FALLBACK_PARENT": 0, "UNKNOWN_CODE": 0, "INVALID_CODE": 0}

print("Memulai parsing data baru...\n")

for item in data_baru:
    parsed = parse_nomor_surat(item)
    if not parsed:
        continue
    
    kode_untuk_cari = parsed['normalized_kode']
    detail, status, kode_cocok = cari_referensi(kode_untuk_cari)
    
    result_entry = {
        "input": item,
        "parsed_components": {
            "kode_raw": parsed['raw_kode'],
            "kode_normalized": parsed['normalized_kode'],
            "nomor": parsed['nomor_surat'],
            "unit": parsed['unit'],
            "tahun": parsed['tahun']
        },
        "validasi": {
            "status": status,
            "kode_dicocokkan": kode_cocok,
            "deskripsi": detail['description'] if detail else "Tidak ditemukan dalam referensi Permendagri 83/2022",
            "level": detail['level'] if detail else 0,
            "hierarki": detail.get('hierarki', []) if detail else []
        }
    }
    
    hasil_parsing.append(result_entry)
    statistik[status] += 1
    
    # Print preview
    print(f"Input: {item}")
    print(f"  -> Kode: {parsed['normalized_kode']} | Status: {status}")
    if detail:
        print(f"  -> Match: {detail['description']} (Level {detail['level']})")
    else:
        print(f"  -> Match: - (Kode tidak dikenali)")
    print("-" * 50)

# Simpan hasil
output_file = 'docs/hasil_parsing_data_lain.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(hasil_parsing, f, indent=2, ensure_ascii=False)

print("\n" + "="*50)
print("RINGKASAN STATISTIK")
print("="*50)
for status, count in statistik.items():
    print(f"{status}: {count}")
print(f"\nTotal Data: {len(hasil_parsing)}")
print(f"Hasil lengkap disimpan di: {output_file}")
