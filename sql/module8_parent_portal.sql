-- Module 8: Parent Portal — run after modules 1–5

-- Homework assignments (class-level)
CREATE TABLE IF NOT EXISTS homework_assignments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
  class_grade TEXT,
  section TEXT,
  subject_id UUID REFERENCES subjects(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  description TEXT,
  assigned_date DATE DEFAULT CURRENT_DATE,
  due_date DATE,
  created_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Exam results (per student)
CREATE TABLE IF NOT EXISTS exam_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  exam_id UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  marks_obtained DECIMAL(6, 2),
  max_marks DECIMAL(6, 2) DEFAULT 100,
  grade TEXT,
  remarks TEXT,
  published_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (exam_id, student_id)
);

-- Fee payment receipts
CREATE TABLE IF NOT EXISTS fee_receipts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  fee_record_id UUID NOT NULL REFERENCES fee_records(id) ON DELETE CASCADE,
  receipt_number TEXT NOT NULL,
  student_id UUID REFERENCES students(id) ON DELETE SET NULL,
  amount_paid DECIMAL(10, 2) NOT NULL,
  payment_date TIMESTAMPTZ DEFAULT NOW(),
  payment_method TEXT DEFAULT 'cash',
  issued_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (school_id, receipt_number)
);

-- Parent complaints / messages to school
DO $$ BEGIN
  CREATE TYPE parent_message_status AS ENUM ('open', 'in_review', 'replied', 'closed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS parent_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  parent_id UUID NOT NULL REFERENCES parents(id) ON DELETE CASCADE,
  student_id UUID REFERENCES students(id) ON DELETE SET NULL,
  subject TEXT NOT NULL,
  message TEXT NOT NULL,
  status parent_message_status DEFAULT 'open',
  admin_reply TEXT,
  replied_at TIMESTAMPTZ,
  replied_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_homework_school_class ON homework_assignments(school_id, class_id);
CREATE INDEX IF NOT EXISTS idx_exam_results_student ON exam_results(student_id);
CREATE INDEX IF NOT EXISTS idx_fee_receipts_fee ON fee_receipts(fee_record_id);
CREATE INDEX IF NOT EXISTS idx_parent_messages_parent ON parent_messages(parent_id);

ALTER TABLE homework_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE fee_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE parent_messages ENABLE ROW LEVEL SECURITY;

-- Staff manage homework & results
CREATE POLICY "School staff manage homework"
  ON homework_assignments FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

CREATE POLICY "School staff manage exam results"
  ON exam_results FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

CREATE POLICY "School staff manage fee receipts"
  ON fee_receipts FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'accountant')
    )
  );

CREATE POLICY "School staff manage parent messages"
  ON parent_messages FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin')
    )
  );

-- Parent read policies (linked children only)
CREATE POLICY "Parents read homework for linked children"
  ON homework_assignments FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role = 'parent')
  );

CREATE POLICY "Parents read exam results for linked children"
  ON exam_results FOR SELECT
  USING (
    student_id IN (
      SELECT psl.student_id FROM parent_student_links psl
      JOIN parents p ON p.id = psl.parent_id
      WHERE p.user_id = auth.uid()
    )
  );

CREATE POLICY "Parents read fee receipts for linked children"
  ON fee_receipts FOR SELECT
  USING (
    student_id IN (
      SELECT psl.student_id FROM parent_student_links psl
      JOIN parents p ON p.id = psl.parent_id
      WHERE p.user_id = auth.uid()
    )
    OR fee_record_id IN (
      SELECT fr.id FROM fee_records fr
      WHERE fr.student_id IN (
        SELECT s.user_id FROM students s
        JOIN parent_student_links psl ON psl.student_id = s.id
        JOIN parents p ON p.id = psl.parent_id
        WHERE p.user_id = auth.uid() AND s.user_id IS NOT NULL
      )
    )
  );

CREATE POLICY "Parents manage own messages"
  ON parent_messages FOR ALL
  USING (
    parent_id IN (SELECT id FROM parents WHERE user_id = auth.uid())
  );

-- Parent read on shared tables (via app service role; optional direct RLS)
CREATE POLICY "Parents read linked student attendance"
  ON student_attendance FOR SELECT
  USING (
    student_id IN (
      SELECT psl.student_id FROM parent_student_links psl
      JOIN parents p ON p.id = psl.parent_id
      WHERE p.user_id = auth.uid()
    )
  );

CREATE POLICY "Parents read linked students"
  ON students FOR SELECT
  USING (
    id IN (
      SELECT psl.student_id FROM parent_student_links psl
      JOIN parents p ON p.id = psl.parent_id
      WHERE p.user_id = auth.uid()
    )
  );

CREATE POLICY "Parents read school announcements"
  ON announcements FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role = 'parent')
  );

CREATE POLICY "Parents read school exams"
  ON exams FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role = 'parent')
  );

CREATE POLICY "Parents read class timetable"
  ON teacher_timetable FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role = 'parent')
  );

CREATE POLICY "Parents read school fees"
  ON fee_records FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role = 'parent')
  );

CREATE POLICY "Super admin full access module8"
  ON homework_assignments FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

CREATE POLICY "Super admin full access exam results"
  ON exam_results FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

CREATE POLICY "Super admin full access fee receipts"
  ON fee_receipts FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

CREATE POLICY "Super admin full access parent messages"
  ON parent_messages FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));
