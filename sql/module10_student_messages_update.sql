-- Student messaging: route to admin or teacher + staff notifications
-- Run after module10_student_portal.sql

ALTER TABLE student_messages
  ADD COLUMN IF NOT EXISTS recipient_type TEXT NOT NULL DEFAULT 'admin';

ALTER TABLE student_messages
  ADD COLUMN IF NOT EXISTS teacher_id UUID REFERENCES teachers(id) ON DELETE SET NULL;

DO $$ BEGIN
  ALTER TABLE student_messages
    ADD CONSTRAINT student_messages_recipient_type_check
    CHECK (recipient_type IN ('admin', 'teacher'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_student_messages_teacher ON student_messages(teacher_id);
CREATE INDEX IF NOT EXISTS idx_student_messages_recipient ON student_messages(recipient_type);

CREATE TABLE IF NOT EXISTS staff_notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
  subject TEXT NOT NULL,
  message TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'general',
  reference_id UUID,
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staff_notifications_user ON staff_notifications(user_id, is_read);

ALTER TABLE staff_notifications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users read own staff notifications" ON staff_notifications;
CREATE POLICY "Users read own staff notifications"
  ON staff_notifications FOR SELECT
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users update own staff notifications" ON staff_notifications;
CREATE POLICY "Users update own staff notifications"
  ON staff_notifications FOR UPDATE
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Super admin full access staff notifications" ON staff_notifications;
CREATE POLICY "Super admin full access staff notifications"
  ON staff_notifications FOR ALL
  USING (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'super_admin'));

DROP POLICY IF EXISTS "Teachers manage assigned student messages" ON student_messages;
CREATE POLICY "Teachers manage assigned student messages"
  ON student_messages FOR ALL
  USING (
    teacher_id IN (SELECT id FROM teachers WHERE user_id = auth.uid())
    AND school_id IN (SELECT school_id FROM user_profiles WHERE id = auth.uid())
  );
