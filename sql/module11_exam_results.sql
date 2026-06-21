-- Module 11: Exam & Result Management — run after module8_parent_portal.sql (subjects, exam_results)

DO $$ BEGIN
  CREATE TYPE exam_term_type AS ENUM ('monthly_test', 'midterm', 'final', 'other');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS exam_terms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  term_type exam_term_type NOT NULL DEFAULT 'monthly_test',
  academic_year TEXT,
  class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
  start_date DATE,
  end_date DATE,
  is_published BOOLEAN DEFAULT FALSE,
  created_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exam_papers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  exam_term_id UUID NOT NULL REFERENCES exam_terms(id) ON DELETE CASCADE,
  subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  max_marks DECIMAL(6, 2) NOT NULL DEFAULT 100,
  pass_marks DECIMAL(6, 2) DEFAULT 33,
  weight_percent DECIMAL(5, 2) DEFAULT 100,
  exam_date DATE,
  sort_order INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (exam_term_id, subject_id)
);

CREATE TABLE IF NOT EXISTS exam_subject_marks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  exam_paper_id UUID NOT NULL REFERENCES exam_papers(id) ON DELETE CASCADE,
  exam_term_id UUID NOT NULL REFERENCES exam_terms(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  marks_obtained DECIMAL(6, 2),
  grade TEXT,
  remarks TEXT,
  entered_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (exam_paper_id, student_id)
);

CREATE TABLE IF NOT EXISTS exam_term_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  exam_term_id UUID NOT NULL REFERENCES exam_terms(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
  total_obtained DECIMAL(8, 2) DEFAULT 0,
  total_max DECIMAL(8, 2) DEFAULT 0,
  percentage DECIMAL(5, 2) DEFAULT 0,
  overall_grade TEXT,
  class_rank INT,
  result_status TEXT DEFAULT 'draft' CHECK (result_status IN ('draft', 'published')),
  shared_with_parents BOOLEAN DEFAULT FALSE,
  published_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (exam_term_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_exam_terms_school ON exam_terms(school_id, class_id);
CREATE INDEX IF NOT EXISTS idx_exam_papers_term ON exam_papers(exam_term_id);
CREATE INDEX IF NOT EXISTS idx_exam_subject_marks_term ON exam_subject_marks(exam_term_id, student_id);
CREATE INDEX IF NOT EXISTS idx_exam_term_results_term ON exam_term_results(exam_term_id);
CREATE INDEX IF NOT EXISTS idx_exam_term_results_student ON exam_term_results(student_id);

ALTER TABLE exam_terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_subject_marks ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_term_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Staff manage exam terms"
  ON exam_terms FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

CREATE POLICY "Staff manage exam papers"
  ON exam_papers FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

CREATE POLICY "Staff manage exam subject marks"
  ON exam_subject_marks FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

CREATE POLICY "Staff manage exam term results"
  ON exam_term_results FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'super_admin', 'teacher')
    )
  );

CREATE POLICY "Students read published term results"
  ON exam_term_results FOR SELECT
  USING (
    result_status = 'published'
    AND student_id IN (SELECT id FROM students WHERE user_id = auth.uid())
  );

CREATE POLICY "Students read own subject marks when published"
  ON exam_subject_marks FOR SELECT
  USING (
    student_id IN (SELECT id FROM students WHERE user_id = auth.uid())
    AND exam_term_id IN (SELECT id FROM exam_terms WHERE is_published = TRUE)
  );

CREATE POLICY "Parents read published term results"
  ON exam_term_results FOR SELECT
  USING (
    result_status = 'published'
    AND student_id IN (
      SELECT psl.student_id FROM parent_student_links psl
      JOIN parents p ON p.id = psl.parent_id
      WHERE p.user_id = auth.uid()
    )
  );

CREATE POLICY "Super admin full access exam terms"
  ON exam_terms FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

CREATE POLICY "Super admin full access exam papers"
  ON exam_papers FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

CREATE POLICY "Super admin full access exam subject marks"
  ON exam_subject_marks FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

CREATE POLICY "Super admin full access exam term results"
  ON exam_term_results FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));
