-- ============================================================
-- Supabase seed: Incision and Drainage of Abscess
-- Run AFTER supabase_setup.sql (no enum changes needed)
-- ============================================================
-- Sources:
--   WHO Surgical Safety Checklist (2009)
--   1472-6920-8-38: Teaching I&D — BMC Medical Education
--   2025 Handout: Incision and Drainage Technique
-- ============================================================


-- 1. Procedure
-- ============================================================

INSERT INTO procedures (id, name, version, source_documents) VALUES (
  'incision_drainage_abscess',
  'Incision and Drainage of Abscess',
  '1.0',
  ARRAY[
    'WHO Surgical Safety Checklist (2009)',
    '1472-6920-8-38: Teaching incision and drainage — BMC Medical Education',
    '2025 Handout: Incision and Drainage Technique'
  ]
);


-- 2. Nodes (16 total)
-- ============================================================

INSERT INTO nodes (id, procedure_id, name, phase, mandatory, optional, safety_critical, actors, required_tools, preconditions) VALUES

  -- Checklist: Patient ID + consent
  ('patient_identification',
   'incision_drainage_abscess',
   'Patient Identification and Consent',
   'checklist', true, false, true,
   ARRAY['physician','nurse'],
   ARRAY['consent_form','patient_wristband'],
   ARRAY[]::TEXT[]),

  -- Checklist: Allergy check
  ('allergy_check',
   'incision_drainage_abscess',
   'Allergy Check (Anesthetic and Antibiotic Allergies)',
   'checklist', true, false, true,
   ARRAY['physician','nurse'],
   ARRAY['patient_chart'],
   ARRAY['patient_identification']),

  -- Setup: Equipment
  ('equipment_preparation',
   'incision_drainage_abscess',
   'Equipment and Supplies Preparation',
   'setup', true, false, false,
   ARRAY['nurse'],
   ARRAY['sterile_tray','scalpel_11_blade','hemostats','packing_gauze','irrigation_syringe','wound_culture_swab','local_anesthetic','syringe_needle','sterile_gloves','drape'],
   ARRAY['allergy_check']),

  -- Checklist: Site marking
  ('site_marking',
   'incision_drainage_abscess',
   'Site Identification and Marking',
   'checklist', true, false, true,
   ARRAY['physician'],
   ARRAY['skin_marker'],
   ARRAY['equipment_preparation']),

  -- Setup: Sterile prep
  ('sterile_preparation',
   'incision_drainage_abscess',
   'Sterile Skin Preparation',
   'setup', true, false, true,
   ARRAY['physician'],
   ARRAY['chlorhexidine_or_betadine','sterile_drape','sterile_gloves'],
   ARRAY['site_marking']),

  -- Setup: Local anesthesia
  ('local_anesthesia',
   'incision_drainage_abscess',
   'Local Anesthesia Administration',
   'setup', true, false, false,
   ARRAY['physician'],
   ARRAY['lidocaine_with_epinephrine','syringe','needle_25g'],
   ARRAY['sterile_preparation']),

  -- Exposure: Incision
  ('incision',
   'incision_drainage_abscess',
   'Incision Over Abscess (Along Skin Lines)',
   'exposure', true, false, true,
   ARRAY['physician'],
   ARRAY['scalpel_11_blade'],
   ARRAY['local_anesthesia']),

  -- Exposure: Drain
  ('drainage_expression',
   'incision_drainage_abscess',
   'Drainage and Expression of Purulent Material',
   'exposure', true, false, false,
   ARRAY['physician'],
   ARRAY['hemostats','gauze'],
   ARRAY['incision']),

  -- Exposure: Break loculations
  ('loculation_breakdown',
   'incision_drainage_abscess',
   'Loculation Breakdown with Hemostat',
   'exposure', true, false, false,
   ARRAY['physician'],
   ARRAY['hemostats'],
   ARRAY['drainage_expression']),

  -- Safety: Irrigate
  ('wound_irrigation',
   'incision_drainage_abscess',
   'Wound Irrigation with Saline',
   'safety', true, false, false,
   ARRAY['physician'],
   ARRAY['irrigation_syringe','normal_saline'],
   ARRAY['loculation_breakdown']),

  -- Safety: Culture (optional)
  ('wound_culture',
   'incision_drainage_abscess',
   'Wound Culture Collection',
   'safety', false, true, false,
   ARRAY['physician'],
   ARRAY['culture_swab'],
   ARRAY['drainage_expression']),

  -- Closure: Pack wound
  ('wound_packing',
   'incision_drainage_abscess',
   'Wound Packing with Gauze Strip',
   'closure', true, false, true,
   ARRAY['physician'],
   ARRAY['packing_gauze_strip','hemostats'],
   ARRAY['wound_irrigation']),

  -- Closure: Dressing
  ('external_dressing',
   'incision_drainage_abscess',
   'External Dressing Application',
   'closure', true, false, false,
   ARRAY['physician','nurse'],
   ARRAY['gauze_pad','adhesive_tape'],
   ARRAY['wound_packing']),

  -- Checklist: Discharge
  ('discharge_instructions',
   'incision_drainage_abscess',
   'Discharge Instructions and Follow-Up',
   'checklist', true, false, true,
   ARRAY['physician','nurse'],
   ARRAY['discharge_paperwork'],
   ARRAY['external_dressing']),

  -- Complication: Bleeding
  ('uncontrolled_bleeding',
   'incision_drainage_abscess',
   'Uncontrolled Bleeding Management',
   'complication', false, true, true,
   ARRAY['physician'],
   ARRAY['pressure_dressing','cautery','sutures'],
   ARRAY['incision']),

  -- Complication: Deep extension
  ('deep_tissue_extension',
   'incision_drainage_abscess',
   'Referral for Deep Tissue Extension',
   'complication', false, true, true,
   ARRAY['physician'],
   ARRAY['referral_form'],
   ARRAY['loculation_breakdown']);


-- 3. Edges (16 total)
-- ============================================================

INSERT INTO edges (procedure_id, from_node, to_node, type) VALUES
  -- Main sequential flow
  ('incision_drainage_abscess', 'patient_identification',  'allergy_check',           'sequential'),
  ('incision_drainage_abscess', 'allergy_check',           'equipment_preparation',   'sequential'),
  ('incision_drainage_abscess', 'equipment_preparation',   'site_marking',            'sequential'),
  ('incision_drainage_abscess', 'site_marking',            'sterile_preparation',     'sequential'),
  ('incision_drainage_abscess', 'sterile_preparation',     'local_anesthesia',        'sequential'),
  ('incision_drainage_abscess', 'local_anesthesia',        'incision',                'sequential'),
  ('incision_drainage_abscess', 'incision',                'drainage_expression',     'sequential'),
  ('incision_drainage_abscess', 'drainage_expression',     'loculation_breakdown',    'sequential'),
  ('incision_drainage_abscess', 'loculation_breakdown',    'wound_irrigation',        'sequential'),
  ('incision_drainage_abscess', 'wound_irrigation',        'wound_packing',           'sequential'),
  ('incision_drainage_abscess', 'wound_packing',           'external_dressing',       'sequential'),
  ('incision_drainage_abscess', 'external_dressing',       'discharge_instructions',  'sequential'),
  -- Optional culture branch
  ('incision_drainage_abscess', 'drainage_expression',     'wound_culture',           'conditional'),
  -- Complication branches
  ('incision_drainage_abscess', 'incision',                'uncontrolled_bleeding',   'conditional'),
  ('incision_drainage_abscess', 'uncontrolled_bleeding',   'wound_irrigation',        'conditional'),
  ('incision_drainage_abscess', 'loculation_breakdown',    'deep_tissue_extension',   'conditional');

