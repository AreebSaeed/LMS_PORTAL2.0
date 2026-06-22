-- Module 14: School-wide exam groups & teacher approval workflow
-- Run after module11_exam_results.sql and module13_class_subjects.sql

CREATE TABLE IF NOT EXISTS exam_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  term_type TEXT NOT NULL CHECK (term_type IN ('midterm', 'final')),
  weight_percent DECIMAL(5, 2) NOT NULL DEFAULT 100,
  academic_year TEXT,
  start_date DATE,
  end_date DATE,
  is_published BOOLEAN DEFAULT FALSE,
  published_at TIMESTAMPTZ,
  created_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE exam_terms
  ADD COLUMN IF NOT EXISTS exam_group_id UUID REFERENCES exam_groups(id) ON DELETE CASCADE;

ALTER TABLE exam_terms
  ADD COLUMN IF NOT EXISTS submission_status TEXT DEFAULT 'pending'
  CHECK (submission_status IN ('pending', 'in_progress', 'submitted', 'approved', 'rejected'));

ALTER TABLE exam_terms
  ADD COLUMN IF NOT EXISTS submitted_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL;

ALTER TABLE exam_terms
  ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ;

ALTER TABLE exam_terms
  ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;

ALTER TABLE exam_terms
  ADD COLUMN IF NOT EXISTS rejection_note TEXT;

CREATE INDEX IF NOT EXISTS idx_exam_groups_school ON exam_groups(school_id);
CREATE INDEX IF NOT EXISTS idx_exam_terms_group ON exam_terms(exam_group_id);

ALTER TABLE exam_groups ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Staff manage exam groups"
  ON exam_groups FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

CREATE POLICY "Super admin full access exam groups"
  ON exam_groups FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));
