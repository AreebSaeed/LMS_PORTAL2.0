-- Track which users have read school/class announcements (run after module1_admin.sql)

CREATE TABLE IF NOT EXISTS announcement_reads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
  announcement_id UUID NOT NULL,
  announcement_type TEXT NOT NULL DEFAULT 'school' CHECK (announcement_type IN ('school', 'class')),
  read_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, announcement_id, announcement_type)
);

CREATE INDEX IF NOT EXISTS idx_announcement_reads_user ON announcement_reads(user_id);

ALTER TABLE announcement_reads ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users manage own announcement reads" ON announcement_reads;
CREATE POLICY "Users manage own announcement reads"
  ON announcement_reads FOR ALL
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Super admin full access announcement reads" ON announcement_reads;
CREATE POLICY "Super admin full access announcement reads"
  ON announcement_reads FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));
