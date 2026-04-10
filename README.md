# 🏛️ The Living Archive - Smart Archive Intelligence System

> **Pilot Project Perundang-undangan (PUU)**  
> *Sistem validasi dan visualisasi arsip cerdas berbasis AI*

## 🌟 Gambaran Umum

**The Living Archive** adalah dashboard interaktif yang menampilkan keindahan transformasi data arsip dari input manual yang berantakan menjadi data terstruktur yang sempurna berkat kecerdasan buatan. Sistem ini berfungsi sebagai:

1. **Cermin Kualitas Data**: Menunjukkan secara real-time kelemahan input manual di Google Sheets
2. **Demo Keunggulan AI**: Menampilkan transformasi "magic" yang dilakukan AI secara otomatis
3. **Alat Evaluasi Kinerja**: Mengukur konsistensi dan akurasi input staf
4. **Pusat Referensi Valid**: Menyediakan hierarki klasifikasi arsip yang terpercaya

## 🚀 Fitur Unggulan

### 1. Dashboard Analitik Real-time
- Metrik kualitas input (akurasi, konsistensi, tren)
- Distribusi status validasi
- Top 10 kode klasifikasi terbanyak
- Grafik tren akurasi kumulatif

### 2. Hierarki Arsip Visual
- Tree map interaktif struktur klasifikasi
- Visualisasi penggunaan kode per direktorat
- Drill-down dari level 1 hingga level 4

### 3. AI Magic Log ⭐
- **Showcase utama** yang menampilkan transformasi data
- Before/After comparison untuk setiap koreksi AI
- Penjelasan kontekstual mengapa AI melakukan koreksi
- Highlight pola kesalahan berulang

### 4. Eksplorasi Data
- Pencarian full-text across semua field
- Filter dinamis per unit kerja dan status
- Detail view lengkap per dokumen
- Export capability

## 📁 Struktur Proyek

```
/workspace/
├── app.py                          # Dashboard Streamlit utama
├── src/
│   ├── parser_nomor_nd.py          # Core parsing engine
│   ├── context_corrector.py        # Contextual auto-correction
│   └── local_code_registry.py      # Local code mapping
├── docs/
│   ├── kodfikasi_arsip_*.json      # Reference data
│   ├── hasil_parsing_*.json        # Parsing results
│   └── DOKUMENTASI_SISTEM_PARSING.md
├── data/                           # Raw data samples
├── dashboard_components/           # Reusable UI components
├── requirements.txt                # Python dependencies
└── README.md                       # Dokumentasi ini
```

## 🛠️ Instalasi & Menjalankan

### Prerequisites
- Python 3.8+
- pip package manager

### Langkah Instalasi

```bash
# 1. Clone atau navigate ke workspace
cd /workspace

# 2. Install dependencies
pip install -r requirements.txt

# 3. Jalankan dashboard
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

Dashboard akan terbuka di: `http://localhost:8501`

## 🎯 Cara Menggunakan untuk Pilot PUU

### Untuk Admin/Supervisor:
1. **Monitor Kualitas Input**: Buka tab "Dashboard Analitik" untuk melihat tren akurasi
2. **Identifikasi Masalah**: Cek "AI Magic Log" untuk melihat kesalahan berulang
3. **Evaluasi Staf**: Gunakan metrik untuk memberikan feedback konstruktif
4. **Export Laporan**: Download data untuk meeting evaluasi

### Untuk Staff Input:
1. **Self-Assessment**: Lihat bagaimana input Anda diproses AI
2. **Belajar dari Kesalahan**: Pahami pola koreksi di "AI Magic Log"
3. **Cari Referensi**: Gunakan tab "Eksplorasi Data" untuk validasi mandiri
4. **Tingkatkan Skor**: Berusaha mencapai 100% exact match

## 📊 Insight Strategis

Berdasarkan analisis 60+ dokumen dari berbagai direktorat:

| Insight | Implikasi |
|---------|-----------|
| 88% kode bisa divalidasi exact | Standar nasional sudah cukup komprehensif |
| 12% butuh koreksi kontekstual | Diperlukan training input yang lebih baik |
| Pola typo sistematik (- vs .) | Perlu validation rule di Google Sheets |
| Kode payung sering disalahgunakan | Perlu guidance spesifik per unit |
| Unit kerja lebih stabil dari kode | Jadikan unit sebagai primary key validasi |

## 🔮 Roadmap Pengembangan

### Phase 1 (✅ Completed)
- [x] Core parsing engine
- [x] Context-aware correction
- [x] Local code registry
- [x] Dashboard MVP

### Phase 2 (In Progress)
- [ ] Live integration dengan Google Sheets API
- [ ] Real-time validation saat input
- [ ] User authentication & role-based access
- [ ] Automated weekly reports

### Phase 3 (Planned)
- [ ] Machine learning untuk pattern recognition
- [ ] Predictive suggestion saat mengetik
- [ ] Mobile-friendly interface
- [ ] Integration dengan sistem arsip nasional

## 🤝 Kontribusi

Proyek ini open untuk kontribusi dari semua agent/AI dalam ekosistem:

```bash
# Agent lain dapat update dengan:
git pull origin main
# Lalu jalankan dashboard untuk melihat perubahan
```

## 📞 Support & Feedback

Untuk pertanyaan atau improvement suggestion:
- Buat issue di repository GitHub
- Diskusi di channel #archive-intelligence
- Demo session setiap Jumat 10:00 WIB

---

<div align="center">

**🏗️ Dibangun dengan ❤️ oleh Tim AI Intelligence**  
*"Mengubah data berantakan menjadi insight berharga"*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-latest-red.svg)](https://streamlit.io/)

</div>
