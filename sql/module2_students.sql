-- Module 2: Student Management — run after schema.sql and module1_admin.sql

DO $$ BEGIN
  CREATE TYPE student_status AS ENUM (
    'active', 'inactive', 'transferred', 'graduated', 'left'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS students (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  user_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  full_name TEXT NOT NULL,
  admission_number TEXT NOT NULL,
  roll_number TEXT,
  date_of_birth DATE,
  gender TEXT CHECK (gender IN ('male', 'female', 'other')),
  class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
  class_grade TEXT,
  section TEXT,
  batch_session TEXT,
  address TEXT,
  contact_number TEXT,
  parent_name TEXT,
  parent_cnic TEXT,
  emergency_contact TEXT,
  previous_school TEXT,
  photo_url TEXT,
  status student_status NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (school_id, admission_number)
);

CREATE TABLE IF NOT EXISTS student_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  file_name TEXT NOT NULL,
  file_url TEXT NOT NULL,
  doc_type TEXT DEFAULT 'general',
  uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS student_academic_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  academic_year TEXT NOT NULL,
  class_grade TEXT,
  section TEXT,
  result_summary TEXT,
  notes TEXT,
  recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_students_school ON students(school_id);
CREATE INDEX IF NOT EXISTS idx_students_name ON students(full_name);
CREATE INDEX IF NOT EXISTS idx_students_roll ON students(roll_number);
CREATE INDEX IF NOT EXISTS idx_students_admission ON students(admission_number);
CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_grade, section);

ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_academic_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "School staff manage students"
  ON students FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin')
    )
  );

CREATE POLICY "School staff manage student documents"
  ON student_documents FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin')
    )
  );

CREATE POLICY "School staff manage academic history"
  ON student_academic_history FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin')
    )
  );

CREATE POLICY "Super admin full access students"
  ON students FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

CREATE POLICY "Super admin full access student documents"
  ON student_documents FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

CREATE POLICY "Super admin full access academic history"
  ON student_academic_history FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

-- Supabase Storage: create bucket "student-documents" (public) in Dashboard → Storage
