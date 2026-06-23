-- Fee challan enhancements: structure link, void/reissue, misc charges, school terms

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS fee_structure_id UUID REFERENCES fee_structures(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS misc_charges DECIMAL(10,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS is_void BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS voided_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS voided_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS superseded_by_id UUID REFERENCES fee_records(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS reissued_from_id UUID REFERENCES fee_records(id) ON DELETE SET NULL;

ALTER TABLE schools
  ADD COLUMN IF NOT EXISTS challan_terms TEXT;

CREATE INDEX IF NOT EXISTS idx_fee_records_class_month
  ON fee_records(school_id, class_id, billing_month)
  WHERE is_void IS NOT TRUE;

CREATE INDEX IF NOT EXISTS idx_fee_records_student_active
  ON fee_records(school_id, student_id)
  WHERE is_void IS NOT TRUE;
