-- Module 13: Class subject assignments — run after module4_teachers.sql

CREATE TABLE IF NOT EXISTS class_subjects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  assigned_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (class_id, subject_id)
);

CREATE INDEX IF NOT EXISTS idx_class_subjects_class ON class_subjects(class_id);
CREATE INDEX IF NOT EXISTS idx_class_subjects_school ON class_subjects(school_id);

ALTER TABLE class_subjects ENABLE ROW LEVEL SECURITY;

CREATE POLICY "School staff manage class subjects"
  ON class_subjects FOR ALL
  USING (school_id IN (
    SELECT school_id FROM user_profiles
    WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
  ));

CREATE POLICY "Super admin full access class subjects"
  ON class_subjects FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));
