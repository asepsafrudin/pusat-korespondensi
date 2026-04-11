"""
Live Archive Intelligence Dashboard - Pilot Project PUU
Menyajikan data arsip secara real-time dengan visualisasi AI yang memukau.
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import psycopg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Konfigurasi Halaman
st.set_page_config(
    page_title="The Living Archive - PUU Pilot",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load Data Referensi dan Hasil Parsing
@st.cache_data
def load_data():
    # Load referensi
    try:
        with open('docs/kodefikasi_arsip_referensi.json', 'r') as f:
            referensi = json.load(f)
    except:
        referensi = []
    
    # Load hasil parsing terbaru (gabungan semua sumber)
    parsed_files = [
        'docs/hasil_parsing_dengan_mapping.json',
        'docs/hasil_parsing_data_lain.json',
        'docs/hasil_parsing_nomor_nd.json',
        'docs/hasil_parsing_uji_baru.json'
    ]
    
    all_records = []
    for pf in parsed_files:
        if os.path.exists(pf):
            try:
                with open(pf, 'r') as f:
                    data = json.load(f)
                    records = []
                    if isinstance(data, list):
                        records = data
                    elif isinstance(data, dict) and 'records' in data:
                        records = data['records']
                    
                    for r in records:
                        # Buat record yang sudah di-flatten
                        flat = {
                            'nomor_nd': r.get('input_asli') or r.get('input') or 'N/A',
                            'perihal': r.get('perihal', 'N/A'),
                        }
                        
                        # Ambil kode klasifikasi
                        flat['kode_normalized'] = (
                            r.get('kode_klasifikasi') or 
                            (r.get('parsed_components', {}) if isinstance(r.get('parsed_components'), dict) else {}).get('kode_normalized') or
                            'N/A'
                        )
                        
                        # Ambil unit kerja
                        flat['unit_kerja'] = (
                            (r.get('deteksi_unit', {}) if isinstance(r.get('deteksi_unit'), dict) else {}).get('unit_kerja') or
                            (r.get('parsed_components', {}) if isinstance(r.get('parsed_components'), dict) else {}).get('unit') or
                            'N/A'
                        )
                        
                        # Ambil status validasi & deskripsi
                        validasi = r.get('validasi_referensi') or r.get('validasi') or {}
                        flat['validation_status'] = validasi.get('status', 'PENDING')
                        flat['deskripsi'] = validasi.get('deskripsi', 'N/A')
                        flat['is_valid'] = flat['validation_status'] == 'EXACT_MATCH'
                        flat['validation_notes'] = (
                            (r.get('analisis_konsistensi', {}) if isinstance(r.get('analisis_konsistensi'), dict) else {}).get('catatan', [''])[0]
                        )
                        
                        all_records.append(flat)
            except Exception as e:
                print(f"Error loading {pf}: {e}")
    
    df = pd.DataFrame(all_records)
    
    # Enrichment: Ambil 'hal' dari database jika tersedia
    try:
        conn_str = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DATABASE')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
        with psycopg.connect(conn_str, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT nomor_nd, hal FROM korespondensi_raw_pool")
                rows = cur.fetchall()
                hal_map = {r[0]: r[1] for r in rows if r[0]}
                
                if not df.empty and 'nomor_nd' in df.columns:
                    # Update 'perihal' berdasarkan mapping nomor_nd
                    df['perihal'] = df['nomor_nd'].map(hal_map).fillna(df['perihal'])
    except Exception as e:
        print(f"Database enrichment failed: {e}")

    return referensi, df

referensi, df_parsed = load_data()

# Database Connection Audit
def check_db_connection():
    try:
        conn_str = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DATABASE')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
        with psycopg.connect(conn_str, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM korespondensi_raw_pool")
                row = cur.fetchone()
                count = row[0] if row else 0
                return True, f"Connected to PostgreSQL ({count} raw records)"
    except Exception as e:
        return False, f"Database Disconnected: {str(e)}"

db_ok, db_msg = check_db_connection()

# Custom CSS untuk tampilan yang memukau
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .success-box {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .ai-magic-box {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        margin: 20px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
</style>
""", unsafe_allow_html=True)

# Header Utama
st.markdown('<h1 class="main-header">🏛️ The Living Archive</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Pilot Project Perundang-undangan (PUU) - Powered by AI Intelligence</p>', unsafe_allow_html=True)
st.divider()

# Sidebar Filter
st.sidebar.header("🔍 Filter Data")

# Audit Status in Sidebar
if db_ok:
    st.sidebar.success(f"🌐 {db_msg}")
else:
    st.sidebar.error(f"❌ {db_msg}")

unit_options = sorted(df_parsed['unit_kerja'].dropna().unique()) if not df_parsed.empty else []
selected_unit = st.sidebar.multiselect("Pilih Unit Kerja", unit_options, default=unit_options[:5])

status_options = ['EXACT_MATCH', 'MAPPED_LOCAL_CODE', 'CONTEXT_CORRECTED', 'FALLBACK_PARENT']
selected_status = st.sidebar.multiselect("Status Validasi", status_options, default=status_options)

if selected_unit:
    df_filtered = df_parsed[df_parsed['unit_kerja'].isin(selected_unit)]
else:
    df_filtered = df_parsed

df_filtered = df_filtered[df_filtered['validation_status'].isin(selected_status)]

# Metric Cards
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_docs = len(df_filtered)
    st.metric("📄 Total Dokumen", f"{total_docs:,}", delta="Real-time")

with col2:
    valid_count = len(df_filtered[df_filtered['is_valid'] == True])
    valid_pct = round((valid_count / total_docs * 100), 1) if total_docs > 0 else 0
    st.metric("✅ Validasi Berhasil", f"{valid_pct}%", delta=f"{valid_count} dokumen")

with col3:
    ai_corrected = len(df_filtered[df_filtered['validation_status'].isin(['CONTEXT_CORRECTED', 'MAPPED_LOCAL_CODE'])])
    st.metric("🤖 Diperbaiki AI", f"{ai_corrected}", delta="Otomatis")

with col4:
    unique_codes = df_filtered['kode_normalized'].nunique()
    st.metric("🏷️ Kode Unik", f"{unique_codes}", delta="Klasifikasi")

st.divider()

# Tab Layout
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard Analitik", "🌳 Hierarki Arsip", "✨ AI Magic Log", "🔎 Eksplorasi Data"])

with tab1:
    st.subheader("📈 Analitik Kinerja Input & Validasi")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        # Distribusi Status Validasi
        status_dist = df_filtered['validation_status'].value_counts().reset_index()
        status_dist.columns = ['Status', 'Jumlah']
        
        fig_pie = px.pie(status_dist, values='Jumlah', names='Status', 
                         title='Distribusi Status Validasi',
                         color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col_chart2:
        # Top Kode Klasifikasi
        top_codes = df_filtered['kode_normalized'].value_counts().head(10).reset_index()
        top_codes.columns = ['Kode', 'Frekuensi']
        
        fig_bar = px.bar(top_codes, x='Kode', y='Frekuensi', 
                         title='10 Kode Klasifikasi Terbanyak',
                         color='Frekuensi',
                         color_continuous_scale='Blues')
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # Trend Kualitas Input (simulasi berdasarkan urutan data)
    st.subheader("📉 Tren Kualitas Input Manual")
    df_filtered['urutan'] = range(len(df_filtered))
    
    # Hitung rolling accuracy
    df_sorted = df_filtered.sort_values('urutan').copy()
    df_sorted['cumulative_accuracy'] = df_sorted['is_valid'].expanding().mean() * 100
    
    fig_trend = px.line(df_sorted, x='urutan', y='cumulative_accuracy',
                        title='Akurasi Kumulatif Input (Semakin ke kanan semakin stabil)',
                        labels={'urutan': 'Urutan Dokumen', 'cumulative_accuracy': 'Akurasi (%)'},
                        markers=True)
    fig_trend.update_traces(line=dict(color='#2a5298', width=3))
    st.plotly_chart(fig_trend, use_container_width=True)
    
    st.info("💡 **Insight**: Grafik ini menunjukkan bagaimana konsistensi input manual berubah seiring waktu. "
            "Fluktuasi menandakan perlunya pelatihan atau panduan input yang lebih jelas.")

with tab2:
    st.subheader("🌳 Pohon Hierarki Klasifikasi Arsip")
    
    # Buat tree visualization sederhana
    hierarchy_data = df_filtered.groupby(['kode_normalized', 'deskripsi']).size().reset_index(name='count')
    
    # Group by level 1 (xxx)
    hierarchy_data['level1'] = hierarchy_data['kode_normalized'].str.split('.').str[0]
    
    level1_counts = hierarchy_data.groupby('level1')['count'].sum().sort_values(ascending=False).head(10)
    
    fig_tree = px.treemap(hierarchy_data, 
                          path=['level1', 'kode_normalized', 'deskripsi'], 
                          values='count',
                          title='Hierarki Penggunaan Kode Klasifikasi',
                          color='count',
                          color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_tree, use_container_width=True)
    
    st.markdown("""
    <div class="success-box">
    <strong>🌟 Keindahan Terstruktur:</strong> Setiap kotak mewakili kategori arsip. Ukuran menunjukkan frekuensi penggunaan.
    Warna hijau menandakan kode yang sering digunakan dengan benar, merah untuk yang perlu perhatian.
    </div>
    """, unsafe_allow_html=True)

with tab3:
    st.subheader("✨ AI Magic Log - Transformasi Data Secara Real-time")
    st.markdown("Saksikan bagaimana AI membersihkan, memperbaiki, dan memperkaya data input manual Anda:")
    
    # Filter hanya yang diperbaiki AI
    ai_magic_df = df_filtered[df_filtered['validation_status'].isin(['CONTEXT_CORRECTED', 'MAPPED_LOCAL_CODE', 'FALLBACK_PARENT'])].copy()
    
    if not ai_magic_df.empty:
        for idx, (_, row) in enumerate(ai_magic_df.head(10).iterrows()):
            original_code = row.get('nomor_nd', '').split('/')[0] if pd.notna(row.get('nomor_nd')) else 'N/A'
            corrected_code = row.get('kode_normalized', 'N/A')
            reason = row.get('validation_notes', '')
            
            st.markdown(f"""
            <div class="ai-magic-box">
                <strong>🪄 Transformasi #{int(idx)+1}</strong><br>
                <b>Input Manual:</b> <code>{original_code}</code><br>
                <b>Output AI:</b> <code style="background:white; color:#2a5298; padding:2px 5px; border-radius:3px;">{corrected_code}</code><br>
                <b>Alasan:</b> {reason}<br>
                <b>Perihal:</b> <em>{row.get('perihal', 'N/A')[:100]}...</em>
            </div>
            """, unsafe_allow_html=True)
        
        if len(ai_magic_df) > 10:
            st.write(f"... dan {len(ai_magic_df) - 10} transformasi lainnya.")
    else:
        st.success("🎉 Tidak ada koreksi diperlukan! Semua input sudah sempurna.")
    
    st.markdown("""
    <div class="warning-box">
    <strong>⚠️ Catatan Penting:</strong> Setiap koreksi AI adalah peluang belajar. 
    Pola kesalahan yang berulang menunjukkan area yang perlu perbaikan dalam prosedur input manual.
    </div>
    """, unsafe_allow_html=True)

with tab4:
    st.subheader("🔎 Eksplorasi Detail Dokumen")
    
    # Search box
    search_query = st.text_input("Cari berdasarkan kode, perihal, atau unit kerja")
    
    if search_query:
        mask = df_filtered.apply(lambda row: 
            search_query.lower() in str(row.get('nomor_nd', '')).lower() or
            search_query.lower() in str(row.get('deskripsi', '')).lower() or
            search_query.lower() in str(row.get('unit_kerja', '')).lower() or
            search_query.lower() in str(row.get('perihal', '')).lower(),
            axis=1
        )
        df_search = df_filtered[mask]
    else:
        df_search = df_filtered
    
    # Display table
    display_cols = ['nomor_nd', 'perihal', 'kode_normalized', 'deskripsi', 'unit_kerja', 'validation_status']
    st.dataframe(df_search[display_cols], use_container_width=True, height=400)
    
    # Detail view
    if not df_search.empty:
        selected_row = st.selectbox("Pilih dokumen untuk melihat detail lengkap", 
                                    df_search['nomor_nd'].tolist())
        row_detail = df_search[df_search['nomor_nd'] == selected_row].iloc[0]
        
        st.expander("📋 Detail Lengkap Dokumen").write(row_detail.to_dict())

# Footer Insight
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; font-style: italic;">
<p>🚀 <strong>The Living Archive</strong> bukan sekadar dashboard, tapi cermin kualitas data kita.</p>
<p>Setiap koreksi AI adalah langkah menuju kesempurnaan sistem arsip digital.</p>
<p><em>"Data yang bersih adalah fondasi keputusan yang bijak."</em></p>
</div>
""", unsafe_allow_html=True)

# Auto-refresh option
if st.checkbox("🔄 Auto-refresh setiap 30 detik (untuk demo live)"):
    import time
    time.sleep(30)
    st.rerun()
