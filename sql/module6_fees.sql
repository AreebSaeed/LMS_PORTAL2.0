-- Module 6: Fee Management — run after module1_admin.sql and module2_students.sql

CREATE TABLE IF NOT EXISTS fee_structures (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  class_id UUID REFERENCES classes(id) ON DELETE CASCADE,
  name TEXT,
  tuition_fee DECIMAL(10, 2) DEFAULT 0,
  admission_fee DECIMAL(10, 2) DEFAULT 0,
  annual_fee DECIMAL(10, 2) DEFAULT 0,
  exam_fee DECIMAL(10, 2) DEFAULT 0,
  transport_fee DECIMAL(10, 2) DEFAULT 0,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (school_id, class_id)
);

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS tuition_fee DECIMAL(10, 2) DEFAULT 0;

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS admission_fee DECIMAL(10, 2) DEFAULT 0;

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS annual_fee DECIMAL(10, 2) DEFAULT 0;

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS exam_fee DECIMAL(10, 2) DEFAULT 0;

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS transport_fee DECIMAL(10, 2) DEFAULT 0;

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS discount DECIMAL(10, 2) DEFAULT 0;

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS fine DECIMAL(10, 2) DEFAULT 0;

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS remaining_dues DECIMAL(10, 2);

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS payment_method TEXT;

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS challan_number TEXT;

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS notes TEXT;

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS class_id UUID REFERENCES classes(id) ON DELETE SET NULL;

ALTER TABLE fee_records
  ADD COLUMN IF NOT EXISTS recorded_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS fee_payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  fee_record_id UUID NOT NULL REFERENCES fee_records(id) ON DELETE CASCADE,
  amount DECIMAL(10, 2) NOT NULL,
  payment_method TEXT DEFAULT 'cash',
  payment_date TIMESTAMPTZ DEFAULT NOW(),
  receipt_number TEXT,
  recorded_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fee_reminders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  fee_record_id UUID REFERENCES fee_records(id) ON DELETE SET NULL,
  parent_id UUID REFERENCES parents(id) ON DELETE SET NULL,
  student_id UUID REFERENCES students(id) ON DELETE SET NULL,
  message TEXT NOT NULL,
  sent_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
  sent_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fee_structures_school ON fee_structures(school_id);
CREATE INDEX IF NOT EXISTS idx_fee_records_challan ON fee_records(school_id, challan_number);
CREATE INDEX IF NOT EXISTS idx_fee_records_billing ON fee_records(school_id, billing_month);
CREATE INDEX IF NOT EXISTS idx_fee_payments_record ON fee_payments(fee_record_id);
CREATE INDEX IF NOT EXISTS idx_fee_reminders_student ON fee_reminders(student_id);

ALTER TABLE fee_structures ENABLE ROW LEVEL SECURITY;
ALTER TABLE fee_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE fee_reminders ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Fee staff manage fee structures" ON fee_structures;
CREATE POLICY "Fee staff manage fee structures"
  ON fee_structures FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'accountant', 'super_admin')
    )
  );

DROP POLICY IF EXISTS "Fee staff manage fee payments" ON fee_payments;
CREATE POLICY "Fee staff manage fee payments"
  ON fee_payments FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'accountant', 'super_admin')
    )
  );

DROP POLICY IF EXISTS "Fee staff manage fee reminders" ON fee_reminders;
CREATE POLICY "Fee staff manage fee reminders"
  ON fee_reminders FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'accountant', 'super_admin')
    )
  );

DROP POLICY IF EXISTS "School staff manage fee records" ON fee_records;
CREATE POLICY "School staff manage fee records"
  ON fee_records FOR ALL
  USING (
    school_id IN (
      SELECT school_id FROM user_profiles
      WHERE id = auth.uid() AND role IN ('school_admin', 'accountant', 'super_admin')
    )
  );

DROP POLICY IF EXISTS "Super admin full access fee structures" ON fee_structures;
CREATE POLICY "Super admin full access fee structures"
  ON fee_structures FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

DROP POLICY IF EXISTS "Super admin full access fee payments" ON fee_payments;
CREATE POLICY "Super admin full access fee payments"
  ON fee_payments FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

DROP POLICY IF EXISTS "Super admin full access fee reminders" ON fee_reminders;
CREATE POLICY "Super admin full access fee reminders"
  ON fee_reminders FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));
