-- Module 12: Homework / Classwork Management — run after module9_teacher_portal.sql

DO $$ BEGIN
  CREATE TYPE homework_type AS ENUM ('homework', 'classwork');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE homework_assignments
  ADD COLUMN IF NOT EXISTS hw_type homework_type DEFAULT 'homework';

ALTER TABLE homework_assignments
  ADD COLUMN IF NOT EXISTS attachment_url TEXT;

ALTER TABLE homework_assignments
  ADD COLUMN IF NOT EXISTS attachment_name TEXT;

ALTER TABLE homework_assignments
  ADD COLUMN IF NOT EXISTS submission_enabled BOOLEAN DEFAULT TRUE;

ALTER TABLE homework_submissions
  ADD COLUMN IF NOT EXISTS teacher_comment TEXT;

ALTER TABLE homework_submissions
  ADD COLUMN IF NOT EXISTS attachment_url TEXT;

ALTER TABLE homework_submissions
  ADD COLUMN IF NOT EXISTS attachment_name TEXT;

ALTER TABLE homework_submissions
  ADD COLUMN IF NOT EXISTS seen_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS homework_views (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  homework_id UUID NOT NULL REFERENCES homework_assignments(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  viewed_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  viewed_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (homework_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_homework_views_student ON homework_views(student_id);
CREATE INDEX IF NOT EXISTS idx_homework_views_hw ON homework_views(homework_id);

ALTER TABLE homework_views ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Staff manage homework views" ON homework_views;
CREATE POLICY "Staff manage homework views"
  ON homework_views FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

DROP POLICY IF EXISTS "Students and parents mark homework seen" ON homework_views;
CREATE POLICY "Students and parents mark homework seen"
  ON homework_views FOR ALL
  USING (
    student_id IN (SELECT id FROM students WHERE user_id = auth.uid())
    OR student_id IN (
      SELECT psl.student_id FROM parent_student_links psl
      JOIN parents p ON p.id = psl.parent_id
      WHERE p.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Super admin full access homework views" ON homework_views;
CREATE POLICY "Super admin full access homework views"
  ON homework_views FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

-- Supabase Storage: create bucket "homework-attachments" (public) in Dashboard → Storage
