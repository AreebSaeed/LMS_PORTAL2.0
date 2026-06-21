-- Module 10: Student Portal — run after module9_teacher_portal.sql

ALTER TABLE students
  ADD COLUMN IF NOT EXISTS login_enabled BOOLEAN DEFAULT FALSE;

ALTER TABLE students
  ADD COLUMN IF NOT EXISTS email TEXT;

-- Student notifications (school → student)
CREATE TABLE IF NOT EXISTS student_notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  subject TEXT NOT NULL,
  message TEXT NOT NULL,
  sent_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  sent_at TIMESTAMPTZ DEFAULT NOW()
);

-- Study materials / class resources
CREATE TABLE IF NOT EXISTS study_materials (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
  subject_id UUID REFERENCES subjects(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  description TEXT,
  file_url TEXT,
  link_url TEXT,
  uploaded_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Student messages to school
DO $$ BEGIN
  CREATE TYPE student_message_status AS ENUM ('open', 'in_review', 'replied', 'closed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS student_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  subject TEXT NOT NULL,
  message TEXT NOT NULL,
  status student_message_status DEFAULT 'open',
  admin_reply TEXT,
  replied_at TIMESTAMPTZ,
  replied_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_student_notifications_student ON student_notifications(student_id);
CREATE INDEX IF NOT EXISTS idx_study_materials_class ON study_materials(class_id);
CREATE INDEX IF NOT EXISTS idx_student_messages_student ON student_messages(student_id);

ALTER TABLE student_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_materials ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_messages ENABLE ROW LEVEL SECURITY;

-- Students read own record
CREATE POLICY "Students read own profile"
  ON students FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Students read own notifications"
  ON student_notifications FOR SELECT
  USING (
    student_id IN (SELECT id FROM students WHERE user_id = auth.uid())
  );

CREATE POLICY "Students manage own messages"
  ON student_messages FOR ALL
  USING (
    student_id IN (SELECT id FROM students WHERE user_id = auth.uid())
  );

CREATE POLICY "Students read class study materials"
  ON study_materials FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role = 'student')
  );

CREATE POLICY "Students submit own homework"
  ON homework_submissions FOR ALL
  USING (
    student_id IN (SELECT id FROM students WHERE user_id = auth.uid())
  );

CREATE POLICY "Students read own attendance"
  ON student_attendance FOR SELECT
  USING (
    student_id IN (SELECT id FROM students WHERE user_id = auth.uid())
  );

CREATE POLICY "Students read own exam results"
  ON exam_results FOR SELECT
  USING (
    student_id IN (SELECT id FROM students WHERE user_id = auth.uid())
  );

CREATE POLICY "Students read school announcements"
  ON announcements FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role = 'student')
  );

CREATE POLICY "Students read class announcements"
  ON class_announcements FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role = 'student')
  );

CREATE POLICY "Students read class timetable"
  ON teacher_timetable FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role = 'student')
  );

CREATE POLICY "Students read homework for class"
  ON homework_assignments FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role = 'student')
  );

CREATE POLICY "Students read school exams"
  ON exams FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role = 'student')
  );

CREATE POLICY "Students read own fees"
  ON fee_records FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role = 'student')
  );

CREATE POLICY "Staff manage student notifications"
  ON student_notifications FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

CREATE POLICY "Staff manage study materials"
  ON study_materials FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

CREATE POLICY "Staff manage student messages"
  ON student_messages FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin')
    )
  );

CREATE POLICY "Super admin full access module10 notifications"
  ON student_notifications FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

CREATE POLICY "Super admin full access study materials"
  ON study_materials FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

CREATE POLICY "Super admin full access student messages"
  ON student_messages FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));
