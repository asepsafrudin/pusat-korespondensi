import json
import os

def merge_enrichment():
    master_path = '/home/aseps/MCP/korespondensi-server/src/master_struktur_bangda2026.json'
    enrichment_path = '/home/aseps/MCP/korespondensi-server/src/Qwen_json_20260416_b2j90or5b.json'
    
    with open(master_path, 'r') as f:
        master = json.load(f)
    
    with open(enrichment_path, 'r') as f:
        enrichment = json.load(f)
        
    enrich_map = {item['unit_id']: item for item in enrichment['detail_enrichment']}
    
    for unit in master['struktur_organisasi_lengkap']['unit_kerja']:
        unit_id = unit['id']
        if unit_id in enrich_map:
            data = enrich_map[unit_id]
            # Merge operational staff
            unit['staf_operasional'] = data.get('staf_operasional', [])
            # Merge unit khusus if exists
            if 'unit_khusus' in data:
                unit['unit_khusus'] = data['unit_khusus']
            # Merge PIC operational details to the right team if possible
            if 'pic_operasional' in data:
                pic = data['pic_operasional']
                for sub in unit.get('sub_unit', []):
                    for team in sub.get('tim_kerja', []):
                        if team.get('nama_tim') == "Penyusunan Perundang-Undangan" or "Perundang-Undangan" in team.get('nama_tim', ''):
                            team['pic_operasional_detail'] = pic

    with open(master_path, 'w') as f:
        json.dump(master, f, indent=2)
    
    print("Successfully merged enrichment data into master_struktur_bangda2026.json")

if __name__ == "__main__":
    merge_enrichment()
