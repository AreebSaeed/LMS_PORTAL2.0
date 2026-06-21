-- Module 4: Teacher / Staff Management — run after schema.sql, module1_admin.sql

DO $$ BEGIN
  CREATE TYPE staff_status AS ENUM ('active', 'inactive', 'on_leave', 'terminated');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS subjects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  code TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (school_id, name)
);

CREATE TABLE IF NOT EXISTS teachers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  user_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  full_name TEXT NOT NULL,
  employee_id TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  cnic TEXT,
  qualification TEXT,
  joining_date DATE,
  designation TEXT DEFAULT 'Teacher',
  login_enabled BOOLEAN DEFAULT FALSE,
  status staff_status NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (school_id, employee_id)
);

CREATE TABLE IF NOT EXISTS teacher_subjects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  assigned_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (teacher_id, subject_id)
);

CREATE TABLE IF NOT EXISTS teacher_classes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  assigned_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (teacher_id, class_id)
);

CREATE TABLE IF NOT EXISTS teacher_timetable (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
  subject_id UUID REFERENCES subjects(id) ON DELETE SET NULL,
  day_of_week TEXT NOT NULL CHECK (day_of_week IN (
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'
  )),
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  room TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$ BEGIN
  CREATE TYPE staff_attendance_status AS ENUM ('present', 'absent', 'late', 'leave');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS teacher_attendance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  status staff_attendance_status NOT NULL DEFAULT 'present',
  check_in TIME,
  check_out TIME,
  notes TEXT,
  UNIQUE (teacher_id, date)
);

CREATE INDEX IF NOT EXISTS idx_teachers_school ON teachers(school_id);
CREATE INDEX IF NOT EXISTS idx_subjects_school ON subjects(school_id);
CREATE INDEX IF NOT EXISTS idx_teacher_timetable ON teacher_timetable(teacher_id);

ALTER TABLE subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE teachers ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_timetable ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_attendance ENABLE ROW LEVEL SECURITY;

CREATE POLICY "School staff manage subjects"
  ON subjects FOR ALL
  USING (school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')));

CREATE POLICY "School staff manage teachers"
  ON teachers FOR ALL
  USING (school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin')));

CREATE POLICY "Teachers read own profile"
  ON teachers FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "School staff manage teacher subjects"
  ON teacher_subjects FOR ALL
  USING (school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')));

CREATE POLICY "School staff manage teacher classes"
  ON teacher_classes FOR ALL
  USING (school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')));

CREATE POLICY "School staff manage timetable"
  ON teacher_timetable FOR ALL
  USING (school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')));

CREATE POLICY "School staff manage teacher attendance"
  ON teacher_attendance FOR ALL
  USING (school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')));

CREATE POLICY "Super admin full access module4"
  ON teachers FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));
