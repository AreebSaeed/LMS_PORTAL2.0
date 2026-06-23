-- Fix fee_records.student_id to reference students (not user_profiles).
-- Required for challan generation when students do not have portal logins yet.
-- Run in Supabase SQL editor after module6_fees.sql.

-- Challan columns (from module15) if not applied yet
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

ALTER TABLE fee_records DROP CONSTRAINT IF EXISTS fee_records_student_id_fkey;

ALTER TABLE fee_records
  ADD CONSTRAINT fee_records_student_id_fkey
  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_fee_records_class_month
  ON fee_records(school_id, class_id, billing_month)
  WHERE is_void IS NOT TRUE;

CREATE INDEX IF NOT EXISTS idx_fee_records_student_active
  ON fee_records(school_id, student_id)
  WHERE is_void IS NOT TRUE;

-- Students: read fee rows stored with students.id
DROP POLICY IF EXISTS "Students read own fees" ON fee_records;
CREATE POLICY "Students read own fees"
  ON fee_records FOR SELECT
  USING (
    student_id IN (SELECT id FROM students WHERE user_id = auth.uid())
    OR student_id = auth.uid()
  );
