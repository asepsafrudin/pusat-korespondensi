import csv
import json
import re
from pathlib import Path

def clean_text(text):
    """Bersihkan teks dari whitespace berlebih dan karakter tidak diinginkan"""
    if not text:
        return ""
    text = text.strip()
    text = text.replace('\n', ' ').replace('\r', '')
    text = re.sub(r'\s+', ' ', text)
    return text

def get_code_level(code):
    """Tentukan level hierarki dari kode (jumlah segmen yang dipisahkan titik)"""
    if not code:
        return 0
    parts = code.split('.')
    return len(parts)

def is_valid_code(text):
    """Cek apakah text adalah kode valid (format xxx atau xxx.x atau xxx.x.x dll)"""
    if not text:
        return False
    return bool(re.match(r'^\d{3}(\.\d+)*$', text))

def parse_csv_to_hierarchy(csv_path):
    """Parse file CSV kodefikasi arsip ke struktur hierarki JSON"""
    
    records = []
    level_parents = {}  # {level: code}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        row_num = 0
        for row in reader:
            row_num += 1
            
            # Skip baris header dan metadata (3 baris pertama)
            if row_num <= 3:
                continue
            
            # Skip baris kosong
            if not any(cell.strip() for cell in row):
                continue
            
            # Cari kolom yang berisi kode
            code_col_idx = -1
            code = ""
            description = ""
            
            # Cek setiap kolom untuk menemukan kode
            for i in range(min(4, len(row))):
                cell = clean_text(row[i])
                if is_valid_code(cell):
                    code_col_idx = i
                    code = cell
                    # Deskripsi ada di kolom berikutnya
                    if i + 1 < len(row):
                        desc_candidate = clean_text(row[i + 1])
                        # Pastikan bukan kode lain
                        if desc_candidate and not is_valid_code(desc_candidate):
                            description = desc_candidate
                    break
            
            if not code:
                continue
            
            # Tentukan level
            level = get_code_level(code)
            
            # Update parent tracking
            if level == 1:
                level_parents = {1: code}
            elif level > 1:
                level_parents[level] = code
            
            # Cari parent_code
            parent_code = None
            if level > 1:
                for parent_level in range(level - 1, 0, -1):
                    if parent_level in level_parents:
                        parent_code = level_parents[parent_level]
                        break
            
            record = {
                "code": code,
                "description": description,
                "level": level,
                "parent_code": parent_code,
                "full_code": code,
                "children": []
            }
            
            records.append(record)
    
    return records

def build_tree(records):
    """Bangun struktur tree dari flat records"""
    code_map = {r["code"]: r for r in records}
    
    root_nodes = []
    
    for record in records:
        if record["level"] == 1:
            root_nodes.append(record)
        elif record["parent_code"]:
            parent = code_map.get(record["parent_code"])
            if parent:
                parent["children"].append(record)
            else:
                root_nodes.append(record)
        else:
            root_nodes.append(record)
    
    return root_nodes

def simplify_for_reference(tree):
    """Sederhanakan struktur untuk referensi dan validasi"""
    simplified = []
    
    def process_node(node):
        simple_node = {
            "code": node["code"],
            "description": node["description"],
            "level": node["level"]
        }
        if node["children"]:
            simple_node["children"] = [process_node(child) for child in node["children"]]
        return simple_node
    
    for node in tree:
        simplified.append(process_node(node))
    
    return simplified

def create_flat_index(tree):
    """Buat index flat untuk validasi cepat"""
    flat_index = {}
    
    def traverse(node):
        code = node["code"]
        flat_index[code] = {
            "description": node["description"],
            "level": node["level"],
            "has_children": len(node["children"]) > 0
        }
        for child in node["children"]:
            traverse(child)
    
    for node in tree:
        traverse(node)
    
    return flat_index

def main():
    csv_path = Path("/workspace/docs/Kodefikasi Arsip Terbaru Bangda 2022 - Pusat.csv")
    output_dir = Path("/workspace/docs")
    
    print(f"Membaca file: {csv_path}")
    
    # Parse CSV
    records = parse_csv_to_hierarchy(csv_path)
    print(f"Ditemukan {len(records)} records")
    
    # Debug: tampilkan beberapa record pertama dan terakhir
    print("\nSample records (first 15):")
    for i, rec in enumerate(records[:15]):
        desc_preview = rec['description'][:50] if rec['description'] else ""
        print(f"  {i}: level={rec['level']}, code={rec['code']}, desc={desc_preview}")
    
    print("\nSample records (dengan level 4):")
    level_4_recs = [r for r in records if r['level'] >= 4][:10]
    for i, rec in enumerate(level_4_recs):
        desc_preview = rec['description'][:50] if rec['description'] else ""
        print(f"  {i}: level={rec['level']}, code={rec['code']}, desc={desc_preview}")
    
    # Bangun tree
    tree = build_tree(records)
    print(f"\nDibangun {len(tree)} root nodes")
    
    # Hitung total nodes di tree
    def count_nodes(nodes):
        count = len(nodes)
        for node in nodes:
            count += count_nodes(node["children"])
        return count
    
    total_in_tree = count_nodes(tree)
    print(f"Total nodes dalam tree: {total_in_tree}")
    
    # Count by level
    level_counts = {}
    for rec in records:
        lvl = rec['level']
        level_counts[lvl] = level_counts.get(lvl, 0) + 1
    print(f"Distribusi level: {level_counts}")
    
    # Sederhanakan untuk referensi
    reference_data = simplify_for_reference(tree)
    
    # Buat flat index untuk validasi
    flat_index = create_flat_index(tree)
    
    # Output 1: Full tree structure
    full_tree_path = output_dir / "kodefikasi_arsip_full.json"
    with open(full_tree_path, 'w', encoding='utf-8') as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)
    print(f"\nFull tree disimpan ke: {full_tree_path}")
    
    # Output 2: Simplified reference data
    reference_path = output_dir / "kodefikasi_arsip_referensi.json"
    with open(reference_path, 'w', encoding='utf-8') as f:
        json.dump(reference_data, f, indent=2, ensure_ascii=False)
    print(f"Referensi disimpan ke: {reference_path}")
    
    # Output 3: Flat index untuk validasi cepat
    index_path = output_dir / "kodefikasi_arsip_index.json"
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(flat_index, f, indent=2, ensure_ascii=False)
    print(f"Index validasi disimpan ke: {index_path}")
    
    # Output 4: Metadata summary
    metadata = {
        "source_file": str(csv_path),
        "total_records": len(records),
        "root_categories": len(tree),
        "total_nodes_in_tree": total_in_tree,
        "level_distribution": {str(k): v for k, v in level_counts.items()},
        "generated_at": "2024",
        "description": "Kodefikasi Arsip sesuai Permendagri No. 83 Tahun 2022",
        "usage": {
            "full_tree": "Struktur lengkap hierarki untuk navigasi",
            "referensi": "Data referensi untuk lookup",
            "index": "Index flat untuk validasi cepat"
        }
    }
    metadata_path = output_dir / "kodefikasi_arsip_metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"Metadata disimpan ke: {metadata_path}")
    
    # Tampilkan sample struktur
    print("\n=== SAMPLE STRUKTUR HIERARKI ===")
    if tree:
        print(f"\nRoot category pertama:")
        print(json.dumps(tree[0], indent=2, ensure_ascii=False)[:1200])

if __name__ == "__main__":
    main()
