INSERT INTO staff_details (unit_id, nama, nip, pangkat, status_kepegawaian, jabatan_fungsional, penugasan_tim, grade_pppk)
SELECT 
  d->>'unit_id', 
  s->>'nama', s->>'nip', s->>'pangkat', 
  s->>'status_kepegawaian', s->>'jabatan_fungsional', 
  s->>'penugasan_tim', s->>'grade_pppk'
FROM master_json, jsonb_array_elements(detail_enrichment) AS d,
     jsonb_array_elements(d->'staf_operasional') AS s;