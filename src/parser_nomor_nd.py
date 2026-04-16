import re
import json
import os

class NomorNDParser:
    """
    Advanced Parsing Engine dengan Cross-Validation Intelligence.
    Memetakan struktur penomoran Sekretariat & Bidang di Bangda.
    """
    
    # Mapping Standar Kode vs Unit (Berdasarkan Diskusi & Konvensi)
    UNIT_CODE_EXPECTATION = {
        "PUU": ["100", "180"],        # Pemeriksaan / Hukum
        "KEU": ["900", "000.9"],      # Keuangan
        "PRC": ["000.3"],             # Perencanaan
        "BU":  ["000.2", "060", "000.6", "000.3"], # Umum / Organisasi / Kearsipan / BMN
        "SET": ["000.2", "800"],      # Sekretariat / Kepegawaian
    }
    
    # Kode yang BOLEH digunakan oleh semua unit (Administrasi Umum)
    UNIVERSAL_ADMIN_PREFIXES = [
        "800",      # Kepegawaian (Cuti, Surat Tugas)
        "000.2",    # Rumah Tangga (ATK, Service AC, Listrik)
        "061",      # Organisasi & Tata Laksana
        "000.4",    # Layanan Pengadaan
        "000.5",    # Humas / Publikasi
        "090"       # Perjalanan Dinas
    ]

    # Kamus Kata Kunci Semantik untuk Validasi Perihal
    SUBSTANCE_KEYWORDS_MAP = {
        "900": ["bayar", "keuangan", "anggaran", "dipa", "honor", "pajak", "biaya", "dana", "rkpd", "belanja"],
        "800": ["cuti", "pensiun", "tugas", "pegawai", "asn", "ijin", "mutasi", "pelantikan", "sk ", "kgp"],
        "100": ["peraturan", "uu", "hukum", "perda", "pergub", "permohonan", "telaahan", "legal", "sidang"],
        "000.2": ["servis", "perbaikan", "atk", "lampu", "ac ", "gedung", "kendaraan", "mobil", "wisma", "rapat"],
        "000.3": ["inventaris", "aset", "barang", "distribusi", "stok"],
        "500": ["pertanian", "pangan", "kehutanan", "energi", "esdm", "tambang", "laut", "ikan", "perikanan", "kebun"],
        "600": ["pekerjaan umum", "jalan", "jembatan", "irigasi", "tataruang", "drainase", "bangunan", "perumahan", "permukiman", "air bersih"]
    }

    def __init__(self, referensi_path='docs/kodefikasi_arsip_referensi.json', struktur_path='src/master_struktur_bangda_2025.json'):
        raw_ref = self._load_json(referensi_path)
        # Flatten referensi (list) menjadi dict datar untuk pencarian cepat O(1)
        self.referensi_map = self._flatten_referensi(raw_ref)
        self.struktur_data = self._load_json(struktur_path)
        self.subdit_map = self._build_subdit_cache()
        
    def _load_json(self, path):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except:
                    return {}
        return {}

    def _flatten_referensi(self, raw_list, flat_dict=None):
        """Secara rekursif mendatarkan pohon referensi JSON"""
        if flat_dict is None:
            flat_dict = {}
        
        if not isinstance(raw_list, list):
            return flat_dict
            
        for item in raw_list:
            code = item.get("code")
            desc = item.get("description") or item.get("uraian")
            if code:
                flat_dict[code] = desc
            
            # Rekursif ke anak-anaknya
            children = item.get("children")
            if children:
                self._flatten_referensi(children, flat_dict)
        
        return flat_dict

    def _build_subdit_cache(self):
        """Membangun cache untuk mempercepat pencarian Subdit SD.I - SD.VI"""
        cache = {}
        units = self.struktur_data.get("struktur_organisasi_lengkap", {}).get("unit_kerja", [])
        
        for unit in units:
            unit_id = unit.get("id", "").replace("_", " ")
            sub_units = unit.get("sub_unit", [])
            for i, sub in enumerate(sub_units):
                sd_key = f"SD.{i+1}"
                # Simpan mapping: (SUPD II, SD.V) -> Nama Subdit
                cache[(unit_id.upper(), sd_key)] = sub.get("nama_subdit") or sub.get("nama_bagian")
        return cache

    def parse(self, raw_input: str, perihal: str = "", asal_data: str = "") -> dict:
        if not raw_input or not isinstance(raw_input, str):
            return {"status": "error", "message": "Input tidak valid", "anomali_score": 100}

        clean_input = raw_input.strip()
        parts = [p.strip() for p in clean_input.split('/')]
        
        mapping = {
            "kode_klasifikasi": None,
            "nomor_urut": None,
            "unit_pengolah": None, 
            "unit_induk": None,
            "nama_subdit_full": None,
            "is_standard": False,
            "is_admin_general": False,
            "anomali_score": 0,
            "is_inferred": False
        }

        # 1. Dekomposisi Struktural & Deteksi Organisasi
        sd_found = None
        directorate_found = None

        if len(parts) > 0:
            mapping["kode_klasifikasi"] = parts[0].replace('-', '.').replace(' ', '')
        if len(parts) > 1:
            mapping["nomor_urut"] = parts[1]

        # Deteksi dari Nomor ND
        for p in parts[2:]:
            p_up = p.upper().replace(' ', '')
            if any(d in p_up for d in ["SUPD", "PEIPD", "SET", "SEKRETARIAT"]):
                directorate_found = p.upper().replace('.', ' ')
                mapping["unit_induk"] = directorate_found
            
            sd_match = re.search(r"SD\.?([IVX]+)", p_up)
            if sd_match:
                sd_found = f"SD.{sd_match.group(1)}"
                mapping["unit_pengolah"] = sd_found
            elif p_up in ["BU", "KEU", "PRC", "PUU"]:
                mapping["unit_pengolah"] = p_up

        # 2. Inteligensi Asal Data (Prioritas Utama jika Nomor Tidak Lengkap)
        if asal_data and not directorate_found:
            # Normalisasi asal_data (Misal: "PEIPD " -> "PEIPD")
            norm_asal = asal_data.strip().upper()
            if any(d in norm_asal for d in ["SUPD", "PEIPD", "SET"]):
                directorate_found = norm_asal
                mapping["unit_induk"] = directorate_found
                mapping["is_inferred"] = True # Ditandai sebagai inferensi dari metadata

        # 3. Lookup Nama Subdit dari Master Struktur
        if sd_found and directorate_found:
            mapping["nama_subdit_full"] = self.subdit_map.get((directorate_found, sd_found))
        
        # 4. Inteligensi Tambahan: Tebak Direktorat jika asal_data juga tidak membantu
        if sd_found and not directorate_found and perihal:
            inferred = self._infer_missing_info(sd_found, perihal)
            if inferred:
                mapping["unit_induk"] = inferred.get("unit_induk")
                mapping["nama_subdit_full"] = inferred.get("nama_subdit")
                mapping["is_inferred"] = True

        # 5. Intelijen Validasi
        validasi_result = self._validate_intelligence(mapping, perihal)
        mapping.update(validasi_result)

        return mapping

    def _infer_missing_info(self, sd_key, perihal):
        """Menebak Direktorat berdasarkan SD.X dan kata kunci Perihal"""
        candidates = []
        perihal_low = perihal.lower()
        
        # Cari semua SD.X yang sama di seluruh direktorat
        for key, subdit_name in self.subdit_map.items():
            dir_id, sub_key = key
            if sub_key == sd_key:
                # Hitung skor kecocokan kata kunci antara nama subdit dan perihal
                score = 0
                subdit_name_low = subdit_name.lower()
                
                # Tokenisasi sederhana
                keywords = subdit_name_low.split()
                for k in keywords:
                    if len(k) > 3 and k in perihal_low:
                        score += 1
                
                candidates.append({
                    "unit_induk": dir_id,
                    "nama_subdit": subdit_name,
                    "score": score
                })
        
        # Urutkan berdasarkan skor tertinggi
        if candidates:
            best_match = max(candidates, key=lambda x: x['score'])
            if best_match['score'] > 0:
                return best_match
        return None

    def _validate_intelligence(self, mapping, perihal):
        report = {
            "is_consistent": True,
            "messages": [],
            "deskripsi_arsip": "Unknown"
        }
        score = 0
        
        kode = mapping["kode_klasifikasi"]
        unit = mapping["unit_pengolah"] # Bisa BU atau SD.V

        if not kode:
            return {"validation_report": report, "anomali_score": 100}

        # Cek apakah ini Kode Administrasi Universal
        is_universal = any(kode.startswith(pref) for pref in self.UNIVERSAL_ADMIN_PREFIXES)
        mapping["is_admin_general"] = is_universal

        # A. Cek Konsistensi Kode vs Unit
        if unit and not is_universal:
            expected_prefixes = self.UNIT_CODE_EXPECTATION.get(unit, [])
            is_match = any(kode.startswith(exp) for exp in expected_prefixes)
            if not is_match and expected_prefixes:
                report["is_consistent"] = False
                report["messages"].append(f"Anomali Unit: Unit {unit} menggunakan kode {kode}")
                score += 30

        # B. Cek Deskripsi Kode dari Referensi MAP (Recursive Lookup)
        desc_found = self.referensi_map.get(kode)
        if desc_found:
            report["deskripsi_arsip"] = desc_found
        elif not is_universal:
            report["messages"].append("Peringatan: Kode tidak ditemukan di referensi")
            score += 20
        
        # C. Validasi Semantik (Menggunakan Exact Word Matching)
        if perihal:
            perihal_low = perihal.lower()
            import re
            
            # Khusus: Deteksi Proses Lintas Fungsi (PUU/Hukum yang diinisiasi Unit Teknis)
            legal_process_keywords = ["izin prakarsa", "rancangan peraturan", "rancangan permendagri", "telaahan hukum"]
            is_legal_workflow = any(re.search(r'\b' + re.escape(kw) + r'\b', perihal_low) for kw in legal_process_keywords)
            
            if is_legal_workflow and unit and unit.startswith("SD"):
                report["messages"].append(f"Info: Inisiasi Regulasi (Proses PUU) oleh unit teknis {unit}")
                # Jangan beri skor anomali tinggi jika itu memang inisiasi regulasi
                score = max(0, score - 20) 

            for base_code, keywords in self.SUBSTANCE_KEYWORDS_MAP.items():
                for k in keywords:
                    pattern = r'\b' + re.escape(k) + r'\b'
                    if re.search(pattern, perihal_low):
                        if not kode.startswith(base_code):
                            # Jika ini adalah workflow legal yang valid, toleransi lebih tinggi
                            if is_legal_workflow and base_code == "100":
                                continue
                                
                            report["messages"].append(f"Anomali Substansi: Tema '{base_code}' terdeteksi lewat kata '{k}', tapi kode '{kode}'")
                            score += 50
                        break
            
            # --- FITUR BARU: Deteksi Kode Terlalu Umum (Specificity Audit) ---
            # Jika kode hanya 3 digit (atau berakhir .0) dan ada anak kode yang lebih cocok
            is_generic = len(kode.split('.')) < 2 or kode.endswith('.0')
            if is_generic:
                # Cari kode yang lebih detail di referensi yang mengandung kata kunci perihal
                suggestions = []
                # Bangun vocab perihal (kumpulan kata unik)
                perihal_tokens = set(re.findall(r'\b\w{2,}\b', perihal_low))
                
                for ref_code, ref_desc in self.referensi_map.items():
                    if ref_code.startswith(kode) and ref_code != kode:
                        # Syarat: Deskripsi di referensi memiliki kata yang muncul di perihal
                        ref_words = set(re.findall(r'\b\w{2,}\b', ref_desc.lower()))
                        # Abaikan kata umum/stopwords
                        stopwords = {'dan', 'yang', 'atau', 'untuk', 'dengan', 'dalam'}
                        keywords_found = (ref_words & perihal_tokens) - stopwords
                        
                        if keywords_found:
                            suggestions.append((ref_code, len(keywords_found)))
                
                if suggestions:
                    # Urutkan berdasarkan jumlah kata kunci yang cocok terbanyak
                    suggestions.sort(key=lambda x: x[1], reverse=True)
                    best_sug_code = suggestions[0][0]
                    report["messages"].append(f"💡 Saran Spesifikasi: Gunakan kode {best_sug_code} ({self.referensi_map.get(best_sug_code)}) agar lebih detail.")

        return {
            "validation_report": report,
            "anomali_score": min(score, 100),
            "is_standard": score < 50
        }

# --- Quick Trial ---
if __name__ == "__main__":
    parser = NomorNDParser()
    # Test Case dengan Subdit Mapping
    test_data = [
        {"no": "900.1/112/SD.VI/SUPD II", "hal": "Laporan Keuangan"}, # SD.VI SUPD II = Statistik & Persandian
        {"no": "100.4.2/45/PUU/SET", "hal": "Rancangan Peraturan"},
        {"no": "800/22/SD.V/SUPD IV", "hal": "Surat Tugas"}           # SD.V SUPD IV = Kepemudaan & OR
    ]
    
    for item in test_data:
        res = parser.parse(item["no"], item.get("hal", ""))
        print(f"INPUT: {item['no']}")
        print(f"  Nama Subdit: {res.get('nama_subdit_full')}")
        print(f"  Unit: {res.get('unit_pengolah')} | Score: {res.get('anomali_score')}")
        print("-" * 50)
