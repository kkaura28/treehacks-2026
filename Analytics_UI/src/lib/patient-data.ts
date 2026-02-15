// Mock patient profiles keyed by procedure_run_id
// In production this would come from an EHR/Supabase table

export interface PatientProfile {
  name: string;
  age: number;
  sex: "M" | "F";
  chief_complaint: string;
  history_of_present_illness: string;
  medical_history: string[];
  medications: { name: string; dose: string; reason: string }[];
  allergies: { substance: string; reaction: string }[];
  vitals: { bp: string; hr: number; temp: string; spo2: number; weight: string };
  lab_results?: { name: string; value: string; flag?: "high" | "low" | "critical" }[];
  social_history?: string;
  notes?: string;
}

export const PATIENT_PROFILES: Record<string, PatientProfile> = {
  // Video 1 — abscess
  "e697291a-5e4c-43f0-b7a1-edb45c0db5c4": {
    name: "Maria Santos",
    age: 32,
    sex: "F",
    chief_complaint: "Painful swelling on left forearm × 5 days",
    history_of_present_illness:
      "32 y/o female presents with a 3 cm erythematous, fluctuant mass on the left volar forearm. Progressive pain and swelling over 5 days. No fever. Denies recent trauma or IV drug use. Works as a line cook — minor cut at work 1 week ago.",
    medical_history: ["None significant"],
    medications: [],
    allergies: [],
    vitals: { bp: "118/74", hr: 78, temp: "98.8°F", spo2: 99, weight: "62 kg" },
    lab_results: [
      { name: "WBC", value: "11.2 K/μL", flag: "high" },
      { name: "CRP", value: "24 mg/L", flag: "high" },
    ],
    social_history: "Non-smoker, social drinker. Works as line cook.",
    notes: "Low-risk patient. Standard I&D protocol appropriate.",
  },

  // Video 2 — abscess
  "30cbac3f-171f-4d3a-9bdb-58e218d02b17": {
    name: "James Mitchell",
    age: 58,
    sex: "M",
    chief_complaint: "Right gluteal abscess × 7 days with worsening pain",
    history_of_present_illness:
      "58 y/o male with PMHx of type 2 DM and hypertension presents with large (5 cm) right gluteal abscess. Started as a small boil 7 days ago, now significantly enlarged with surrounding cellulitis extending 3 cm. Low-grade fever (100.2°F). Reports sitting at desk job worsens pain. History of recurrent folliculitis in this area.",
    medical_history: ["Type 2 Diabetes Mellitus (A1c 8.1%)", "Hypertension", "Recurrent folliculitis", "Obesity (BMI 34)"],
    medications: [
      { name: "Metformin", dose: "1000 mg BID", reason: "Diabetes" },
      { name: "Lisinopril", dose: "20 mg daily", reason: "Hypertension" },
      { name: "Aspirin", dose: "81 mg daily", reason: "Cardiovascular prophylaxis" },
    ],
    allergies: [{ substance: "Penicillin", reaction: "Rash and hives" }],
    vitals: { bp: "142/88", hr: 92, temp: "100.2°F", spo2: 97, weight: "104 kg" },
    lab_results: [
      { name: "WBC", value: "14.8 K/μL", flag: "high" },
      { name: "Glucose", value: "218 mg/dL", flag: "high" },
      { name: "A1c", value: "8.1%", flag: "high" },
      { name: "CRP", value: "68 mg/L", flag: "high" },
      { name: "Creatinine", value: "1.1 mg/dL" },
    ],
    social_history: "Former smoker (quit 5 years ago). Sedentary desk job. No alcohol.",
    notes: "Higher risk: uncontrolled DM impairs wound healing, penicillin allergy limits antibiotic options. Consider clindamycin or TMP-SMX post-procedure. Monitor glucose peri-operatively. Aspirin may increase bleeding — assess risk/benefit of holding.",
  },

  // Video 3 — abscess (Gemini 3 Pro run)
  "3d3120d0-0b36-4afb-98e9-48f5569d01ec": {
    name: "Sarah Chen",
    age: 45,
    sex: "F",
    chief_complaint: "Left axillary abscess × 4 days",
    history_of_present_illness:
      "45 y/o female on Warfarin for atrial fibrillation presents with 4 cm fluctuant left axillary abscess. Developed after shaving. Moderate pain, no systemic symptoms. INR this morning was 2.8.",
    medical_history: ["Atrial fibrillation (diagnosed 2023)", "Hypothyroidism", "Previous DVT (2022)"],
    medications: [
      { name: "Warfarin", dose: "5 mg daily", reason: "Atrial fibrillation / DVT prophylaxis" },
      { name: "Levothyroxine", dose: "75 mcg daily", reason: "Hypothyroidism" },
      { name: "Metoprolol", dose: "50 mg BID", reason: "Rate control for AFib" },
    ],
    allergies: [{ substance: "Penicillin", reaction: "Anaphylaxis" }],
    vitals: { bp: "128/78", hr: 72, temp: "99.1°F", spo2: 98, weight: "68 kg" },
    lab_results: [
      { name: "INR", value: "2.8", flag: "critical" },
      { name: "WBC", value: "12.4 K/μL", flag: "high" },
      { name: "TSH", value: "2.1 mIU/L" },
      { name: "Hemoglobin", value: "12.8 g/dL" },
    ],
    social_history: "Non-smoker, occasional wine. Office manager.",
    notes: "CRITICAL: Patient on Warfarin with INR 2.8 — expect increased bleeding during incision. Have hemostatic agents ready. Do NOT use penicillin-based antibiotics (anaphylaxis history) — clindamycin is safe. Coordinate with cardiology re: anticoagulation management peri-procedure.",
  },

  // Mock lap chole
  "aa4ca99f-1ab3-4a4f-9d42-d00393b97222": {
    name: "Robert Kim",
    age: 67,
    sex: "M",
    chief_complaint: "Recurrent right upper quadrant pain — symptomatic cholelithiasis",
    history_of_present_illness:
      "67 y/o male with 6-month history of postprandial RUQ pain. Ultrasound confirmed multiple gallstones with gallbladder wall thickening. Two ED visits for biliary colic in past 3 months. No evidence of choledocholithiasis on MRCP. Scheduled for elective laparoscopic cholecystectomy.",
    medical_history: [
      "Type 2 Diabetes Mellitus (A1c 7.4%)",
      "GERD",
      "Myocardial infarction (2021) — 1 stent to LAD",
      "Hyperlipidemia",
      "Mild COPD",
    ],
    medications: [
      { name: "Metformin", dose: "500 mg BID", reason: "Diabetes" },
      { name: "Omeprazole", dose: "20 mg daily", reason: "GERD" },
      { name: "Aspirin", dose: "81 mg daily", reason: "Post-MI prophylaxis" },
      { name: "Atorvastatin", dose: "40 mg daily", reason: "Hyperlipidemia" },
      { name: "Tiotropium", dose: "18 mcg inhaled daily", reason: "COPD" },
      { name: "Clopidogrel", dose: "75 mg daily", reason: "Post-stent antiplatelet" },
    ],
    allergies: [{ substance: "Sulfa drugs", reaction: "Stevens-Johnson syndrome" }],
    vitals: { bp: "136/82", hr: 68, temp: "98.4°F", spo2: 95, weight: "82 kg" },
    lab_results: [
      { name: "WBC", value: "7.2 K/μL" },
      { name: "ALT", value: "52 U/L", flag: "high" },
      { name: "AST", value: "48 U/L", flag: "high" },
      { name: "Bilirubin", value: "1.4 mg/dL" },
      { name: "INR", value: "1.0" },
      { name: "Glucose", value: "156 mg/dL", flag: "high" },
      { name: "Creatinine", value: "1.2 mg/dL" },
      { name: "SpO2", value: "95%", flag: "low" },
    ],
    social_history: "Former smoker (40 pack-years, quit 2021). No alcohol. Retired engineer.",
    notes: "Complex patient: dual antiplatelet therapy (aspirin + clopidogrel) — coordinate with cardiology on hold/bridge. Mild COPD with SpO2 95% — anesthesia team aware, may need post-op supplemental O2. Sulfa allergy (SJS) — avoid all sulfonamides. Mildly elevated LFTs consistent with biliary pathology.",
  },
};

export function formatPatientContext(p: PatientProfile): string {
  let ctx = `Patient: ${p.name}, ${p.age}${p.sex}, ${p.vitals.weight}\n`;
  ctx += `Chief Complaint: ${p.chief_complaint}\n\n`;
  ctx += `HPI: ${p.history_of_present_illness}\n\n`;
  ctx += `Medical History: ${p.medical_history.join("; ")}\n\n`;
  if (p.medications.length > 0) {
    ctx += `Medications:\n${p.medications.map(m => `  - ${m.name} ${m.dose} (${m.reason})`).join("\n")}\n\n`;
  } else {
    ctx += `Medications: None\n\n`;
  }
  if (p.allergies.length > 0) {
    ctx += `Allergies:\n${p.allergies.map(a => `  - ${a.substance}: ${a.reaction}`).join("\n")}\n\n`;
  } else {
    ctx += `Allergies: NKDA\n\n`;
  }
  ctx += `Vitals: BP ${p.vitals.bp}, HR ${p.vitals.hr}, Temp ${p.vitals.temp}, SpO2 ${p.vitals.spo2}%\n\n`;
  if (p.lab_results && p.lab_results.length > 0) {
    ctx += `Labs:\n${p.lab_results.map(l => `  - ${l.name}: ${l.value}${l.flag ? ` [${l.flag.toUpperCase()}]` : ""}`).join("\n")}\n\n`;
  }
  if (p.social_history) ctx += `Social History: ${p.social_history}\n\n`;
  if (p.notes) ctx += `Clinical Notes: ${p.notes}\n`;
  return ctx;
}

