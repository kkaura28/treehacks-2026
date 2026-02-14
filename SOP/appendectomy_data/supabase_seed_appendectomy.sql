-- ============================================================
-- Supabase seed: Laparoscopic Appendectomy
-- Run AFTER supabase_setup.sql (no enum changes needed)
-- ============================================================
-- Sources:
--   WHO Surgical Safety Checklist (2009)
--   SAGES Guidelines for Laparoscopic Appendectomy (2010)
--   Sohn et al. — Standardized technique of laparoscopic
--   appendectomy, IJSU (2017) DOI:10.1016/j.ijsu.2017.11.028
-- ============================================================


-- 1. Procedure
-- ============================================================

INSERT INTO procedures (id, name, version, source_documents) VALUES (
  'laparoscopic_appendectomy',
  'Laparoscopic Appendectomy',
  '1.0',
  ARRAY[
    'WHO Surgical Safety Checklist (2009)',
    'SAGES Guidelines for Laparoscopic Appendectomy (2010)',
    'Standardized technique of laparoscopic appendectomy - IJSU (Sohn et al. 2017)'
  ]
);


-- 2. Nodes (21 total)
-- ============================================================

INSERT INTO nodes (id, procedure_id, name, phase, mandatory, optional, safety_critical, actors, required_tools, preconditions) VALUES

  -- Checklist: Sign In
  ('who_sign_in',
   'laparoscopic_appendectomy',
   'WHO Sign In',
   'checklist', true, false, true,
   ARRAY['anesthesiologist','nurse','surgeon'],
   ARRAY['who_checklist'],
   ARRAY[]::TEXT[]),

  -- Setup: General anesthesia
  ('general_anesthesia',
   'laparoscopic_appendectomy',
   'Induction of General Anesthesia',
   'setup', true, false, false,
   ARRAY['anesthesiologist'],
   ARRAY['anesthesia_machine','endotracheal_tube','iv_access'],
   ARRAY['who_sign_in']),

  -- Setup: Positioning
  ('patient_positioning',
   'laparoscopic_appendectomy',
   'Patient Positioning (Supine, Left Arm Tucked)',
   'setup', true, false, false,
   ARRAY['surgeon','nurse'],
   ARRAY['operating_table'],
   ARRAY['general_anesthesia']),

  -- Setup: Antibiotic prophylaxis (SAGES: single-dose preoperative)
  ('antibiotic_prophylaxis',
   'laparoscopic_appendectomy',
   'Antibiotic Prophylaxis',
   'setup', true, false, true,
   ARRAY['anesthesiologist'],
   ARRAY['iv_antibiotics'],
   ARRAY['patient_positioning']),

  -- Checklist: Time Out
  ('who_time_out',
   'laparoscopic_appendectomy',
   'WHO Time Out',
   'checklist', true, false, true,
   ARRAY['surgeon','anesthesiologist','nurse'],
   ARRAY['who_checklist'],
   ARRAY['antibiotic_prophylaxis']),

  -- Setup: Pneumoperitoneum (Veress or Hasson)
  ('establish_pneumoperitoneum',
   'laparoscopic_appendectomy',
   'Establish Pneumoperitoneum',
   'setup', true, false, false,
   ARRAY['surgeon'],
   ARRAY['veress_needle','co2_insufflator'],
   ARRAY['who_time_out']),

  -- Setup: 3-port placement (Sohn: umbilical 12mm, suprapubic 5mm, LLQ 5mm)
  ('trocar_placement',
   'laparoscopic_appendectomy',
   'Trocar Placement (3-Port Technique)',
   'setup', true, false, false,
   ARRAY['surgeon','assistant'],
   ARRAY['trocar_12mm','trocars_5mm','laparoscope'],
   ARRAY['establish_pneumoperitoneum']),

  -- Exposure: Diagnostic survey
  ('diagnostic_laparoscopy',
   'laparoscopic_appendectomy',
   'Diagnostic Laparoscopy and Abdominal Survey',
   'exposure', true, false, false,
   ARRAY['surgeon'],
   ARRAY['laparoscope','camera'],
   ARRAY['trocar_placement']),

  -- Exposure: Identify & mobilize appendix (Trendelenburg + left tilt)
  ('appendix_identification',
   'laparoscopic_appendectomy',
   'Identification and Mobilization of Appendix',
   'exposure', true, false, true,
   ARRAY['surgeon','assistant'],
   ARRAY['grasper','dissector'],
   ARRAY['diagnostic_laparoscopy']),

  -- Exposure: Mesoappendix dissection (Sohn: bipolar/ultrasonic)
  ('mesoappendix_dissection',
   'laparoscopic_appendectomy',
   'Mesoappendix Dissection',
   'exposure', true, false, true,
   ARRAY['surgeon'],
   ARRAY['bipolar_cautery','dissector','ultrasonic_scalpel'],
   ARRAY['appendix_identification']),

  -- Division: Ligate mesoappendix vessels
  ('mesoappendix_vessel_ligation',
   'laparoscopic_appendectomy',
   'Mesoappendix Vessel Ligation',
   'division', true, false, true,
   ARRAY['surgeon'],
   ARRAY['bipolar_cautery','clip_applier','ultrasonic_scalpel'],
   ARRAY['mesoappendix_dissection']),

  -- Division: Appendix base ligation (SAGES: endoloop or stapler)
  ('appendix_base_ligation',
   'laparoscopic_appendectomy',
   'Appendix Base Ligation (Endoloop or Stapler)',
   'division', true, false, true,
   ARRAY['surgeon'],
   ARRAY['endoloop','endoscopic_stapler'],
   ARRAY['mesoappendix_vessel_ligation']),

  -- Division: Transection
  ('appendix_transection',
   'laparoscopic_appendectomy',
   'Appendix Transection',
   'division', true, false, true,
   ARRAY['surgeon'],
   ARRAY['laparoscopic_scissors','endoscopic_stapler'],
   ARRAY['appendix_base_ligation']),

  -- Removal: Bag retrieval (SAGES: always use retrieval bag)
  ('specimen_retrieval',
   'laparoscopic_appendectomy',
   'Specimen Retrieval in Bag',
   'removal', true, false, false,
   ARRAY['surgeon'],
   ARRAY['retrieval_bag'],
   ARRAY['appendix_transection']),

  -- Safety: Check stump and hemostasis
  ('hemostasis_and_stump_check',
   'laparoscopic_appendectomy',
   'Hemostasis and Appendiceal Stump Integrity Check',
   'safety', true, false, true,
   ARRAY['surgeon'],
   ARRAY['laparoscope','irrigation_suction'],
   ARRAY['specimen_retrieval']),

  -- Safety: Irrigation if contaminated (optional)
  ('irrigation',
   'laparoscopic_appendectomy',
   'Peritoneal Irrigation (if Contamination Present)',
   'safety', false, true, false,
   ARRAY['surgeon'],
   ARRAY['irrigation_suction','warm_saline'],
   ARRAY['hemostasis_and_stump_check']),

  -- Closure: Desufflation
  ('desufflation',
   'laparoscopic_appendectomy',
   'Desufflation and Trocar Removal',
   'closure', true, false, false,
   ARRAY['surgeon'],
   ARRAY['trocar_12mm','trocars_5mm'],
   ARRAY['hemostasis_and_stump_check']),

  -- Closure: Port sites
  ('port_site_closure',
   'laparoscopic_appendectomy',
   'Port Site Closure',
   'closure', true, false, false,
   ARRAY['surgeon'],
   ARRAY['sutures','skin_closure_device'],
   ARRAY['desufflation']),

  -- Checklist: Sign Out
  ('who_sign_out',
   'laparoscopic_appendectomy',
   'WHO Sign Out',
   'checklist', true, false, true,
   ARRAY['surgeon','anesthesiologist','nurse'],
   ARRAY['who_checklist'],
   ARRAY['port_site_closure']),

  -- Complication: Bleeding
  ('bleeding_control',
   'laparoscopic_appendectomy',
   'Bleeding Control (Mesoappendix or Stump)',
   'complication', false, true, true,
   ARRAY['surgeon'],
   ARRAY['clip_applier','cautery','irrigation_suction','sutures'],
   ARRAY['mesoappendix_dissection']),

  -- Complication: Conversion to open
  ('conversion_to_open',
   'laparoscopic_appendectomy',
   'Conversion to Open Appendectomy',
   'complication', false, true, true,
   ARRAY['surgeon','assistant','nurse'],
   ARRAY['open_surgery_tray','retractors','sutures'],
   ARRAY['bleeding_control']);


-- 3. Edges (24 total)
-- ============================================================

INSERT INTO edges (procedure_id, from_node, to_node, type) VALUES
  -- Main sequential flow
  ('laparoscopic_appendectomy', 'who_sign_in',                   'general_anesthesia',              'sequential'),
  ('laparoscopic_appendectomy', 'general_anesthesia',            'patient_positioning',             'sequential'),
  ('laparoscopic_appendectomy', 'patient_positioning',           'antibiotic_prophylaxis',          'sequential'),
  ('laparoscopic_appendectomy', 'antibiotic_prophylaxis',        'who_time_out',                    'sequential'),
  ('laparoscopic_appendectomy', 'who_time_out',                  'establish_pneumoperitoneum',      'sequential'),
  ('laparoscopic_appendectomy', 'establish_pneumoperitoneum',    'trocar_placement',                'sequential'),
  ('laparoscopic_appendectomy', 'trocar_placement',              'diagnostic_laparoscopy',          'sequential'),
  ('laparoscopic_appendectomy', 'diagnostic_laparoscopy',        'appendix_identification',         'sequential'),
  ('laparoscopic_appendectomy', 'appendix_identification',       'mesoappendix_dissection',         'sequential'),
  ('laparoscopic_appendectomy', 'mesoappendix_dissection',       'mesoappendix_vessel_ligation',    'sequential'),
  ('laparoscopic_appendectomy', 'mesoappendix_vessel_ligation',  'appendix_base_ligation',          'sequential'),
  ('laparoscopic_appendectomy', 'appendix_base_ligation',        'appendix_transection',            'sequential'),
  ('laparoscopic_appendectomy', 'appendix_transection',          'specimen_retrieval',              'sequential'),
  ('laparoscopic_appendectomy', 'specimen_retrieval',            'hemostasis_and_stump_check',      'sequential'),
  -- Optional irrigation branch
  ('laparoscopic_appendectomy', 'hemostasis_and_stump_check',    'irrigation',                      'conditional'),
  ('laparoscopic_appendectomy', 'hemostasis_and_stump_check',    'desufflation',                    'sequential'),
  ('laparoscopic_appendectomy', 'irrigation',                    'desufflation',                    'sequential'),
  -- Closure chain
  ('laparoscopic_appendectomy', 'desufflation',                  'port_site_closure',               'sequential'),
  ('laparoscopic_appendectomy', 'port_site_closure',             'who_sign_out',                    'sequential'),
  -- Complication branches
  ('laparoscopic_appendectomy', 'mesoappendix_dissection',       'bleeding_control',                'conditional'),
  ('laparoscopic_appendectomy', 'appendix_transection',          'bleeding_control',                'conditional'),
  ('laparoscopic_appendectomy', 'bleeding_control',              'conversion_to_open',              'conditional'),
  ('laparoscopic_appendectomy', 'bleeding_control',              'hemostasis_and_stump_check',      'conditional'),
  ('laparoscopic_appendectomy', 'conversion_to_open',            'hemostasis_and_stump_check',      'sequential');

