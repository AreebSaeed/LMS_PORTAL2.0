-- Schools table
CREATE TABLE schools (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  address TEXT,
  phone TEXT,
  email TEXT,
  logo_url TEXT,
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'disabled')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Roles enum
CREATE TYPE user_role AS ENUM (
  'super_admin',
  'school_admin',
  'accountant',
  'teacher',
  'student',
  'parent'
);

-- User profiles (extends Supabase Auth users)
CREATE TABLE user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name TEXT NOT NULL,
  role user_role NOT NULL,
  school_id UUID REFERENCES schools(id) ON DELETE SET NULL,
  phone TEXT,
  avatar_url TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row-Level Security
ALTER TABLE schools ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Super admin full access on schools"
  ON schools FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles
      WHERE id = auth.uid() AND role = 'super_admin'
    )
  );

CREATE POLICY "Users read own school"
  ON schools FOR SELECT
  USING (
    id IN (
      SELECT school_id FROM user_profiles WHERE id = auth.uid()
    )
  );

CREATE POLICY "Users read own profile"
  ON user_profiles FOR SELECT
  USING (id = auth.uid());

CREATE POLICY "Super admin full access on profiles"
  ON user_profiles FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles
      WHERE id = auth.uid() AND role = 'super_admin'
    )
  );

-- After creating super admin in Supabase Auth, seed their profile:
-- INSERT INTO user_profiles (id, full_name, role)
-- VALUES ('<auth-user-uuid>', 'Super Admin', 'super_admin');
