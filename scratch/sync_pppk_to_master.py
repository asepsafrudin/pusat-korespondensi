import json
import os
from datetime import datetime

# Paths
source_pppk_path = '/home/aseps/MCP/korespondensi-server/src/pppk_bangda_filtered.json'
master_path = '/home/aseps/MCP/korespondensi-server/src/master_struktur_bangda2026.json'
output_path = '/home/aseps/MCP/korespondensi-server/src/master_struktur_bangda2026_enriched.json'

def sync():
    # Load data
    with open(source_pppk_path, 'r') as f:
        pppk_data = json.load(f)
    
    with open(master_path, 'r') as f:
        master_data = json.load(f)

    # Dictionary for easy lookup of units in master
    master_units = {u['id']: u for u in master_data['struktur_organisasi_lengkap']['unit_kerja']}
    
    stats = {
        "total_pppk_added": 0,
        "placed_in_subunits": 0,
        "placed_in_poliklinik": 0,
        "gender_dist": {"Laki-laki": 0, "Perempuan": 0, "Tidak Diketahui": 0}
    }

    # Process source PPPK units
    for src_unit in pppk_data['struktur_organisasi_lengkap']['unit_kerja']:
        unit_id = src_unit['id']
        if unit_id not in master_units:
            continue
            
        target_unit = master_units[unit_id]
        
        # Ensure target has staf_operasional list
        if 'staf_operasional' not in target_unit:
            target_unit['staf_operasional'] = []
            
        # NIPs already in master (to avoid duplicates)
        existing_nips = {s['nip'].replace(' ', '') for s in target_unit['staf_operasional'] if s.get('nip')}

        for person in src_unit['staf_operasional']:
            nip_clean = person['nip'].replace(' ', '')
            
            # Skip if already exists
            if nip_clean in existing_nips:
                continue
            
            # Update stats
            stats["total_pppk_added"] += 1
            stats["gender_dist"][person.get("jenis_kelamin", "Tidak Diketahui")] += 1
            
            # Special Case: Poliklinik
            if person['penugasan_tim'] == "Poliklinik Pratama":
                if 'unit_khusus' not in target_unit:
                    target_unit['unit_khusus'] = {}
                if 'poliklinik_pratama' not in target_unit['unit_khusus']:
                    target_unit['unit_khusus']['poliklinik_pratama'] = []
                
                # Check if already in poliklinik
                poli_nips = {p['nip'].replace(' ', '') for p in target_unit['unit_khusus']['poliklinik_pratama'] if p.get('nip')}
                if nip_clean not in poli_nips:
                    target_unit['unit_khusus']['poliklinik_pratama'].append(person)
                    stats["placed_in_poliklinik"] += 1
                continue

            # Try to place in specific sub_unit tim if it exists
            placed = False
            if 'sub_unit' in target_unit:
                for sub in target_unit['sub_unit']:
                    # Check against Bagian or Subdit names
                    sub_name = sub.get('nama_bagian') or sub.get('nama_subdit') or ""
                    if sub_name.upper() == person['penugasan_tim'].upper():
                        if 'staf' not in sub: sub['staf'] = []
                        sub['staf'].append(person)
                        placed = True
                        stats["placed_in_subunits"] += 1
                        break
            
            # Always add to main staf_operasional for the unit as primary database
            target_unit['staf_operasional'].append(person)

    # Update Global Metadata
    master_data['metadata']['updated_at'] = datetime.now().isoformat()
    master_data['metadata']['enrichment_stats'] = stats
    master_data['metadata']['changelog'].append(f"ENRICH: Added {stats['total_pppk_added']} PPPK staff from {os.path.basename(source_pppk_path)}")

    # Save
    with open(output_path, 'w') as f:
        json.dump(master_data, f, indent=2)
    
    print(f"Sync complete. New master saved to {output_path}")
    print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    sync()
