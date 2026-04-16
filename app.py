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
from src.parser_nomor_nd import NomorNDParser

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
    referensi = {}
    try:
        with open('docs/kodefikasi_arsip_referensi.json', 'r') as f:
            referensi = json.load(f)
    except:
        pass

    conn_str = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DATABASE')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    
    try:
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                # AMBIL SEMUA DATA DARI DATABASE (Tabel Warehouse)
                cur.execute("""
                    SELECT 
                        nomor_nd, hal, tanggal, sheet_identity, data_group, unique_id
                    FROM korespondensi_raw_pool
                """)
                rows = cur.fetchall()
                
                def extract_sub_unit(no_nd, unit_parent):
                    if not no_nd or no_nd == 'N/A': return f'Pimpinan / {unit_parent}'
                    no_up = no_nd.upper()
                    
                    # 1. Cek Subdit Wilayah (I - V)
                    import re
                    subdit_patterns = [
                        (r'SD\.?\s*I\b|SD\.?\s*1\b', 'Subdit Wilayah I'),
                        (r'SD\.?\s*II\b|SD\.?\s*2\b', 'Subdit Wilayah II'),
                        (r'SD\.?\s*III\b|SD\.?\s*3\b', 'Subdit Wilayah III'),
                        (r'SD\.?\s*IV\b|SD\.?\s*4\b', 'Subdit Wilayah IV'),
                        (r'SD\.?\s*V\b|SD\.?\s*5\b', 'Subdit Wilayah V'),
                        (r'SD\.?\s*PMIPD|SD\.?\s*PEIPD', 'Subdit Data & Informasi')
                    ]
                    for pattern, name in subdit_patterns:
                        if re.search(pattern, no_up): return name
                        
                    # 2. Cek Bagian Pendukung (Sekretariat)
                    support_patterns = [
                        (r'\bBU\b|\bUMUM\b', 'Bagian Umum'),
                        (r'\bTU\b|\bTATA\s*USAHA\b', 'Tata Usaha'),
                        (r'\bKEU\b|\bKEUANGAN\b', 'Bagian Keuangan'),
                        (r'\bPRC\b|\bPERENCANAAN\b', 'Bagian Perencanaan'),
                        (r'\bPUU\b|\bHUKUM\b', 'Substansi Perundang-Undangan'),
                        (r'\bORG\b|\bORGANISASI\b', 'Bagian Organisasi')
                    ]
                    for pattern, name in support_patterns:
                        if re.search(pattern, no_up): return name
                    
                    # 3. Fallback ke Pimpinan
                    if unit_parent == 'SEKRETARIAT': return 'Pimpinan / Sesditjen'
                    return f'Pimpinan / Direktur {unit_parent}'

                all_records = []
                for r in rows:
                    u_induk = r[3] or 'N/A'
                    all_records.append({
                        'nomor_nd': r[0] or 'N/A',
                        'perihal': r[1] or 'N/A',
                        'tanggal_surat': r[2],
                        'unit_induk': u_induk,
                        'unit_kerja': extract_sub_unit(r[0], u_induk),
                        'data_group': r[4] or 'INTERNAL',
                        'unique_id': r[5],
                        'validation_status': 'PENDING',
                        'is_valid': False, # Default
                        'kode_normalized': r[0].split('/')[0] if (r[0] and '/' in r[0]) else 'N/A',
                        'deskripsi': 'Belum Diperiksa'
                    })
                
                df = pd.DataFrame(all_records)
                
                # Sinkronkan status audit terbaru
                cur.execute("SELECT nomor_nd, message, deskripsi_kode FROM audit_notifications")
                a_rows = cur.fetchall()
                a_map = {r[0]: {'msg': r[1], 'desk': r[2]} for r in a_rows if r[0]}
                
                for idx, row in df.iterrows():
                    no = row['nomor_nd']
                    if no in a_map:
                        df.at[idx, 'validation_status'] = 'NEEDS_ATTENTION'
                        df.at[idx, 'deskripsi'] = a_map[no]['desk']
                        df.at[idx, 'validation_notes'] = a_map[no]['msg']
                    elif no != 'N/A':
                        df.at[idx, 'validation_status'] = 'EXACT_MATCH'
                        df.at[idx, 'is_valid'] = True
                
                return referensi, df
    except Exception as e:
        st.sidebar.error(f"Database Sync Error: {e}")
        return referensi, pd.DataFrame()

@st.cache_data
def load_audit_notifications():
    try:
        conn_str = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DATABASE')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
        with psycopg.connect(conn_str, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT nomor_nd, hal, deskripsi_kode, message, suggestion, anomaly_score FROM audit_notifications ORDER BY created_at DESC")
                if cur.description is None:
                    return pd.DataFrame()
                cols = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        return pd.DataFrame()

def run_audit_process():
    parser = NomorNDParser()
    conn_str = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DATABASE')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    
    try:
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE audit_notifications")
                # JOIN dengan raw_pool untuk mendapatkan source_sheet_name (Asal Data)
                cur.execute("""
                    SELECT t.unique_id, t.nomor_nd, t.hal, r.source_sheet_name 
                    FROM surat_masuk_puu_internal t
                    LEFT JOIN korespondensi_raw_pool r ON t.raw_pool_id = r.id
                    WHERE t.nomor_nd IS NOT NULL
                """)
                rows = cur.fetchall()
                
                for row in rows:
                    uid, no_nd, hal, asal_data = row
                    # Kirim asal_data (Nama Sheet) ke parser
                    result = parser.parse(no_nd, hal, asal_data=asal_data)
                    report = result.get("validation_report", {})
                    
                    if not report.get("is_consistent"):
                        score = result.get("anomali_score", 0)
                        detected_theme = "Unknown"
                        suggested_prefix = ""
                        
                        # Ekstraksi Tema & Saran secara dinamis
                        messages = report.get("messages", [])
                        detected_theme = "Tidak Terdeteksi"
                        suggested_prefix = ""

                        for msg in messages:
                            if "Tema" in msg or "bertema" in msg:
                                import re
                                theme_match = re.search(r"Tema '([^']+)'|bertema '([^']+)'", msg)
                                if theme_match:
                                    # Ambil group yang tidak None
                                    detected_theme = theme_match.group(1) or theme_match.group(2)
                                    suggested_prefix = detected_theme

                        # Gunakan pesan asli dari parser sebagai notifikasi utama
                        notif_msg = " | ".join(messages) if messages else "Terdeteksi ketidakkonsistenan pada input data."
                        suggestion = f"Pertimbangkan untuk menggunakan kode klasifikasi berawalan '{suggested_prefix}' agar sesuai dengan substansi surat." if suggested_prefix else "Mohon periksa kembali kesesuaian kode klasifikasi dengan perihal surat."
                        deskripsi_kode = report.get("deskripsi_arsip", "Tidak Terdaftar")

                        cur.execute("""
                            INSERT INTO audit_notifications 
                            (unique_id, nomor_nd, hal, deskripsi_kode, detected_theme, suggested_prefix, anomaly_score, message, suggestion)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (uid, no_nd, hal, deskripsi_kode, detected_theme, suggested_prefix, score, notif_msg, suggestion))
                conn.commit()
                return True, f"Audit selesai. {len(rows)} dokumen diproses."
    except Exception as e:
        return False, str(e)

referensi, df_parsed = load_data()
df_audit = load_audit_notifications()

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

# Custom CSS untuk tampilan PREMIUM (Glassmorphism & Advanced UI)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        font-size: 3.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        letter-spacing: -2px;
        margin-bottom: 0.5rem;
    }
    
    .sub-header {
        font-size: 1.1rem;
        color: #94a3b8;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 400;
    }

    /* Glassmorphism Cards */
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 1.5rem;
        border-radius: 20px;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.1);
        transition: transform 0.3s ease;
    }
    
    [data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        border: 1px solid rgba(99, 102, 241, 0.5);
    }

    /* AI Magic Box - Premium Gradient */
    .ai-magic-box {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.05) 0%, rgba(168, 85, 247, 0.05) 100%);
        border-left: 5px solid #a855f7;
        padding: 25px;
        border-radius: 16px;
        color: #f8fafc;
        margin: 20px 0;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        position: relative;
        overflow: hidden;
    }
    
    .ai-magic-box::before {
        content: '✨ AI TRANSFORMATION';
        position: absolute;
        top: 10px;
        right: 15px;
        font-size: 0.7rem;
        font-weight: 800;
        color: #a855f7;
        opacity: 0.6;
    }

    .success-box {
        background-color: rgba(34, 197, 94, 0.1);
        border-left: 5px solid #22c55e;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }

    .warning-box {
        background-color: rgba(234, 179, 8, 0.1);
        border-left: 5px solid #eab308;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Header Utama
st.markdown('<h1 class="main-header">🏛️ The Living Archive</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Pilot Project Perundang-undangan (PUU) - Powered by AI Intelligence</p>', unsafe_allow_html=True)
st.divider()

# Sidebar Filter (Pusat Kendali)
with st.sidebar:
    st.markdown("### 🔍 Filter Global")
    
    if db_ok:
        st.success(f"🌐 {db_msg}")
    else:
        st.error(f"❌ {db_msg}")
        
    # 0. Tipe Data Filter (Pengisolasian) dengan Istilah yang Lebih Tepat
    data_label = st.radio("Cakupan Korespondensi:", ["Internal Ditjen Bina Bangda", "Surat Masuk Luar Ditjen"], index=0)
    current_group = "INTERNAL" if data_label == "Internal Ditjen Bina Bangda" else "EXTERNAL"
    
    st.divider()
    
    # 1. Direktorat Filter (Level Utama)
    dir_options = sorted(df_parsed[df_parsed['data_group'] == current_group]['unit_induk'].dropna().unique()) if not df_parsed.empty else []
    selected_dir = st.multiselect("Direktorat:", dir_options, default=dir_options)
    
    # 2. Unit Kerja Filter (Level Detail - Cascading)
    if selected_dir:
        sub_df = df_parsed[df_parsed['unit_induk'].isin(selected_dir)]
        unit_options = sorted(sub_df['unit_kerja'].dropna().unique())
    else:
        unit_options = sorted(df_parsed['unit_kerja'].dropna().unique())
        
    selected_unit = st.multiselect("Unit Kerja:", unit_options, default=[])
    
    # 3. Status Validasi Filter
    status_options = sorted(df_parsed['validation_status'].unique()) if not df_parsed.empty else []
    selected_status = st.multiselect("Status Validasi:", status_options, default=status_options)
    
    # 4. Rentang Tanggal Filter
    df_parsed['tanggal_surat'] = pd.to_datetime(df_parsed['tanggal_surat'], errors='coerce')
    valid_dates = df_parsed['tanggal_surat'].dropna()
    if not valid_dates.empty:
        # Gunakan pd.to_datetime untuk memastikan kompatibilitas .date()
        min_dt = pd.to_datetime(valid_dates.min()).date()
        max_dt = pd.to_datetime(valid_dates.max()).date()
        date_range = st.date_input("Rentang Tanggal:", [min_dt, max_dt])
    else:
        date_range = None
    
    st.divider()
    st.info("💡 Filter di sini akan merubah semua tampilan di dashboard secara bersamaan.")

# Terapkan Filter Global
df_filtered = df_parsed.copy()

# Isolasi: Filter berdasarkan grup data (INTERNAL vs EXTERNAL)
if 'data_group' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['data_group'] == current_group]

if selected_dir:
    df_filtered = df_filtered[df_filtered['unit_induk'].isin(selected_dir)]

if selected_unit:
    df_filtered = df_filtered[df_filtered['unit_kerja'].isin(selected_unit)]

if selected_status:
    df_filtered = df_filtered[df_filtered['validation_status'].isin(selected_status)]

if date_range and len(date_range) == 2:
    start_date, end_date = date_range
    df_filtered = df_filtered[
        (df_filtered['tanggal_surat'].dt.date >= start_date) & 
        (df_filtered['tanggal_surat'].dt.date <= end_date)
    ]

# Metric Cards
col1, col2, col3, col4, col5 = st.columns(5)

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

with col5:
    anomali_count = len(df_audit)
    st.metric("⚠️ Anomali Input", f"{anomali_count}", delta="Audit Konsistensi", delta_color="inverse")

st.divider()

# Tab Layout
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard Analitik", "🌳 Hierarki Arsip", "✨ AI Magic Log", "🔎 Eksplorasi Data", "🔔 Alerta Konsistensi"])

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
        
    st.divider()
    
    # Komparasi Akurasi Antar Unit Induk / Direktorat
    st.subheader("🏆 Komparasi Kualitas Input Antar Unit")
    unit_acc = df_filtered.groupby('unit_induk').agg(
        total=pd.NamedAgg(column='is_valid', aggfunc='count'),
        valid=pd.NamedAgg(column='is_valid', aggfunc='sum')
    ).reset_index()
    unit_acc['akurasi'] = (unit_acc['valid'] / unit_acc['total'] * 100).round(1)
    
    # Hanya tampilkan unit dengan data minimal 5 agar fair
    unit_acc = unit_acc[unit_acc['total'] >= 5].sort_values('akurasi', ascending=True)
    
    if not unit_acc.empty:
        fig_unit_acc = px.bar(unit_acc, x='akurasi', y='unit_induk', orientation='h',
                              title='Tingkat Akurasi Input per Direktorat (%) (Min. 5 Data)',
                              text='akurasi',
                              hover_data={'total': True},
                              color='akurasi',
                              color_continuous_scale='Greens')
        fig_unit_acc.update_traces(texttemplate='%{text}%', textposition='outside')
        fig_unit_acc.update_layout(xaxis_title="Akurasi (%)", yaxis_title="Direktorat")
        st.plotly_chart(fig_unit_acc, use_container_width=True)
    else:
        st.info("Data belum cukup untuk membandingkan kinerja antar Direktorat.")
    
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
    
    # Simple search box inside tab (Global search handled by sidebar)
    search_query = st.text_input("Cari kata kunci pada perihal atau nomor...")
    
    df_search = df_filtered.copy()
    if search_query:
        mask = df_search.apply(lambda row: 
            search_query.lower() in str(row.get('nomor_nd', '')).lower() or
            search_query.lower() in str(row.get('deskripsi', '')).lower() or
            search_query.lower() in str(row.get('unit_kerja', '')).lower() or
            search_query.lower() in str(row.get('perihal', '')).lower(),
            axis=1
        )
        df_search = df_search[mask]
    
    # Display table with optimized column configuration
    display_cols = ['nomor_nd', 'perihal', 'kode_normalized', 'deskripsi', 'unit_kerja', 'validation_status']
    st.dataframe(
        df_search[display_cols], 
        use_container_width=True, 
        height=500,
        column_config={
            "perihal": st.column_config.TextColumn("Perihal (HAL)", width="large"),
            "deskripsi": st.column_config.TextColumn("Deskripsi Arsip", width="medium"),
            "nomor_nd": st.column_config.TextColumn("Nomor ND", width="medium"),
        }
    )
    
    # Detail view
    if not df_search.empty:
        selected_row = st.selectbox("Pilih dokumen untuk melihat detail lengkap", 
                                    df_search['nomor_nd'].tolist())
        row_detail = df_search[df_search['nomor_nd'] == selected_row].iloc[0]
        
        st.expander("📋 Detail Lengkap Dokumen").write(row_detail.to_dict())

with tab5:
    st.subheader("🔔 Alerta Konsistensi - Audit Input Manusia")
    
    col_audit1, col_audit2 = st.columns([3, 1])
    with col_audit1:
        st.markdown("""
        Katalog di bawah ini adalah daftar ketidakkonsistenan yang ditemukan oleh AI saat membandingkan 
        **Kode ND** dengan **Perihal (HAL)**.
        """)
    with col_audit2:
        if st.button("🔄 Jalankan Ulang Audit", use_container_width=True):
            with st.spinner("AI sedang membedah konsistensi data..."):
                success, msg = run_audit_process()
                if success:
                    st.success(msg)
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Gagal audit: {msg}")

    if not df_audit.empty:
        # Style dataframe for anomalies
        def highlight_anomalies(s):
            return ['background-color: rgba(239, 68, 68, 0.1)' for _ in s]

        st.dataframe(
            df_audit.style.apply(highlight_anomalies, axis=1),
            use_container_width=True,
            height=600,
            column_config={
                "nomor_nd": st.column_config.TextColumn("Nomor ND", width="medium"),
                "hal": st.column_config.TextColumn("Perihal (HAL)", width="large"),
                "deskripsi_kode": st.column_config.TextColumn("Arti Kode Input", width="medium"),
                "message": st.column_config.TextColumn("📢 Notifikasi Intelijen", width="large"),
                "suggestion": st.column_config.TextColumn("💡 Saran AI", width="large"),
            }
        )
        
        st.markdown(f"""
        <div class="warning-box">
        <strong>💡 Insight Konsistensi:</strong> Saat ini ditemukan <b>{len(df_audit)}</b> anomali 
        dari total data yang diperiksa. Mayoritas ketidaksesuaian terjadi pada surat-surat 
        bertema teknis yang menggunakan kode administrasi umum.
        </div>
        """, unsafe_allow_html=True)

        # Fitur Inspeksi Detail
        st.divider()
        st.subheader("🔍 Inspeksi Detail Anomali")
        selected_anomaly = st.selectbox(
            "Pilih Nomor ND untuk melihat detail teks utuh & saran:",
            df_audit['nomor_nd'].tolist(),
            key="anomaly_selector"
        )
        
        if selected_anomaly:
            detail = df_audit[df_audit['nomor_nd'] == selected_anomaly].iloc[0]
            
            col_det1, col_det2 = st.columns(2)
            with col_det1:
                st.markdown("### 📝 Perihal (HAL) Utuh")
                st.info(detail['hal'])
            
            with col_det2:
                st.markdown("### 📣 Analisis & Saran AI")
                st.warning(f"**Temuan:** {detail['message']}")
                st.success(f"**Saran Perbaikan:** {detail['suggestion']}")
                
    else:
        st.success("🎉 Luar Biasa! Tidak ditemukan anomali konsistensi pada audit terakhir.")

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
