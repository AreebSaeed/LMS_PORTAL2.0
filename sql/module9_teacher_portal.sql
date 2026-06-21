-- Module 9: Teacher Portal — run after module8_parent_portal.sql

-- Link homework to teacher record
ALTER TABLE homework_assignments
  ADD COLUMN IF NOT EXISTS teacher_id UUID REFERENCES teachers(id) ON DELETE SET NULL;

-- Student homework submissions
DO $$ BEGIN
  CREATE TYPE homework_submission_status AS ENUM ('submitted', 'late', 'graded', 'missing');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS homework_submissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  homework_id UUID NOT NULL REFERENCES homework_assignments(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  status homework_submission_status DEFAULT 'submitted',
  notes TEXT,
  submitted_at TIMESTAMPTZ DEFAULT NOW(),
  graded_at TIMESTAMPTZ,
  UNIQUE (homework_id, student_id)
);

-- Class-level announcements by teachers
CREATE TABLE IF NOT EXISTS class_announcements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  teacher_id UUID NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  body TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_homework_teacher ON homework_assignments(teacher_id);
CREATE INDEX IF NOT EXISTS idx_homework_submissions_hw ON homework_submissions(homework_id);
CREATE INDEX IF NOT EXISTS idx_class_announcements_teacher ON class_announcements(teacher_id);

ALTER TABLE homework_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_announcements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Teachers manage homework submissions"
  ON homework_submissions FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

CREATE POLICY "Teachers manage class announcements"
  ON class_announcements FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

CREATE POLICY "Parents read homework submissions for linked children"
  ON homework_submissions FOR SELECT
  USING (
    student_id IN (
      SELECT psl.student_id FROM parent_student_links psl
      JOIN parents p ON p.id = psl.parent_id
      WHERE p.user_id = auth.uid()
    )
  );

CREATE POLICY "Super admin full access module9 homework submissions"
  ON homework_submissions FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

CREATE POLICY "Super admin full access class announcements"
  ON class_announcements FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));
