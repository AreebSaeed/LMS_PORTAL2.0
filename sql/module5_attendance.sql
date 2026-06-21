-- Module 5: Attendance Management — run after module2_students.sql

DO $$ BEGIN
  CREATE TYPE student_attendance_status AS ENUM ('present', 'absent', 'late', 'leave');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS student_attendance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
  class_grade TEXT,
  section TEXT,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  status student_attendance_status NOT NULL DEFAULT 'present',
  notes TEXT,
  marked_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  is_submitted BOOLEAN DEFAULT FALSE,
  submitted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (student_id, date)
);

CREATE INDEX IF NOT EXISTS idx_student_attendance_school_date ON student_attendance(school_id, date);
CREATE INDEX IF NOT EXISTS idx_student_attendance_class ON student_attendance(class_id, date);
CREATE INDEX IF NOT EXISTS idx_student_attendance_status ON student_attendance(status, date);

ALTER TABLE student_attendance ENABLE ROW LEVEL SECURITY;

CREATE POLICY "School staff manage student attendance"
  ON student_attendance FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

CREATE POLICY "Super admin full access student attendance"
  ON student_attendance FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

-- Uses existing teacher_attendance from module4_teachers.sql for staff attendance
