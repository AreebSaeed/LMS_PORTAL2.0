-- Module 1: Admin Dashboard — run after schema.sql

-- Classes
CREATE TABLE IF NOT EXISTS classes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  grade TEXT,
  section TEXT,
  teacher_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Attendance
DO $$ BEGIN
  CREATE TYPE attendance_status AS ENUM ('present', 'absent', 'late', 'excused');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS attendance_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
  class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  status attendance_status NOT NULL DEFAULT 'present',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (student_id, date)
);

-- Fees
DO $$ BEGIN
  CREATE TYPE fee_status AS ENUM ('paid', 'pending', 'partial', 'overdue');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS fee_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
  amount DECIMAL(10, 2) NOT NULL,
  amount_paid DECIMAL(10, 2) DEFAULT 0,
  status fee_status NOT NULL DEFAULT 'pending',
  due_date DATE,
  paid_at TIMESTAMPTZ,
  billing_month DATE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Exams
CREATE TABLE IF NOT EXISTS exams (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
  exam_date DATE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Announcements
CREATE TABLE IF NOT EXISTS announcements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  body TEXT,
  author_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Admissions
CREATE TABLE IF NOT EXISTS admissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  student_name TEXT NOT NULL,
  grade TEXT,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE fee_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE exams ENABLE ROW LEVEL SECURITY;
ALTER TABLE announcements ENABLE ROW LEVEL SECURITY;
ALTER TABLE admissions ENABLE ROW LEVEL SECURITY;

-- School staff read policies (school_admin, accountant, teacher)
DROP POLICY IF EXISTS "School staff read classes" ON classes;
CREATE POLICY "School staff read classes"
  ON classes FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid())
  );

DROP POLICY IF EXISTS "School staff read attendance" ON attendance_records;
CREATE POLICY "School staff read attendance"
  ON attendance_records FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid())
  );

DROP POLICY IF EXISTS "School staff read fees" ON fee_records;
CREATE POLICY "School staff read fees"
  ON fee_records FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid())
  );

DROP POLICY IF EXISTS "School staff read exams" ON exams;
CREATE POLICY "School staff read exams"
  ON exams FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid())
  );

DROP POLICY IF EXISTS "School staff read announcements" ON announcements;
CREATE POLICY "School staff read announcements"
  ON announcements FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid())
  );

DROP POLICY IF EXISTS "School admin manage announcements" ON announcements;
CREATE POLICY "School admin manage announcements"
  ON announcements FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role = 'school_admin'
    )
  );

DROP POLICY IF EXISTS "School staff read admissions" ON admissions;
CREATE POLICY "School staff read admissions"
  ON admissions FOR SELECT
  USING (
    school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid())
  );

DROP POLICY IF EXISTS "Super admin full access classes" ON classes;
CREATE POLICY "Super admin full access classes"
  ON classes FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

DROP POLICY IF EXISTS "Super admin full access attendance" ON attendance_records;
CREATE POLICY "Super admin full access attendance"
  ON attendance_records FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

DROP POLICY IF EXISTS "Super admin full access fees" ON fee_records;
CREATE POLICY "Super admin full access fees"
  ON fee_records FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

DROP POLICY IF EXISTS "Super admin full access exams" ON exams;
CREATE POLICY "Super admin full access exams"
  ON exams FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

DROP POLICY IF EXISTS "Super admin full access announcements" ON announcements;
CREATE POLICY "Super admin full access announcements"
  ON announcements FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

DROP POLICY IF EXISTS "Super admin full access admissions" ON admissions;
CREATE POLICY "Super admin full access admissions"
  ON admissions FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));
