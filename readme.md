# School Management Portal

Multi-role school management system built with Flask + Supabase.

## Roles
| Role         | Access Level                        |
|--------------|-------------------------------------|
| super_admin  | All schools, all users, system-wide |
| school_admin | Own school — users and settings     |
| accountant   | Own school — fees and finance       |
| teacher      | Own school — classes and attendance |
| student      | Own school — subjects and results   |
| parent       | Own school — child progress and fees|

## Setup

1. Clone the repo and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your Supabase credentials.

3. Run the SQL schema in your Supabase SQL Editor:
   ```
   sql/schema.sql
   ```

4. Create your super admin user in Supabase Auth (Authentication → Users),
   then insert their profile:
   ```sql
   INSERT INTO user_profiles (id, full_name, role)
   VALUES ('<uuid-from-supabase-auth>', 'Your Name', 'super_admin');
   ```

5. Start the app:
   ```bash
   python app.py
   ```
   Visit: http://localhost:5000

6. For the Admin Dashboard (Module 1), also run in Supabase SQL Editor:
   ```
   sql/module1_admin.sql
   ```

7. For Student Management (Module 2), run:
   ```
   sql/module2_students.sql
   ```
   Then create a **Storage** bucket named `student-documents` (public) in Supabase Dashboard → Storage.

   Admin access: log in as `school_admin` → **Students** in sidebar or `/students`.

8. For Parent Management (Module 3), run:
   ```
   sql/module3_parents.sql
   ```

   Admin access: **Parents** in sidebar or `/parents`.

9. For Teacher / Staff Management (Module 4), run:
   ```
   sql/module4_teachers.sql
   ```

   Admin access: **Teachers** in sidebar or `/teachers`.

10. For Attendance Management (Module 5), run:
   ```
   sql/module5_attendance.sql
   ```

   - **Teachers:** log in as `teacher` → **Attendance** in sidebar or `/attendance/teacher`
     - Mark daily attendance (present, absent, late, leave)
     - Save draft or submit to admin
   - **Admin:** **Attendance** in sidebar or `/attendance/admin`
     - Daily and monthly reports, absent/late lists
     - Export CSV, notify parents of absences, edit records
     - Teacher attendance uses `teacher_attendance` from Module 4

11. For Fee Management (Module 6), run:
   ```
   sql/module6_fees.sql
   ```
   Requires Module 2 (students) and Module 3 (parents for reminders).

   - **Admin / Accountant:** log in as `school_admin` or `accountant` → `/fees`
     - Create class-wise fee structure (tuition, transport, admission, annual, exam)
     - Generate monthly fee challans per class
     - Record payments (full or partial), apply discounts/scholarships and late fines
     - View paid, unpaid, and defaulter reports
     - Generate receipts, print or download PDF
     - Send fee reminders to linked parents
   - **Parents/Students:** fee status and receipts in `/portal/fees` and `/learn/fees`

12. For Parent Portal (Module 8), run:
   ```
   sql/module8_parent_portal.sql
   ```

   Prerequisites: parent must have login enabled (Module 3) and children linked via **Parents → Edit → Link Students**.

   - **Parents:** log in as `parent` → redirected to `/portal`
     - Dashboard: attendance summary, pending fees, homework, results, announcements, upcoming exams
     - Child profile, daily/monthly attendance, fees & receipts, homework, exam results
     - Class timetable, school announcements, notifications inbox
     - Send messages / complaints to school

13. For Teacher Portal (Module 9), run:
   ```
   sql/module9_teacher_portal.sql
   ```

   Prerequisites: teacher must have login enabled (Module 4) with classes, subjects, and timetable assigned.

   - **Teachers:** log in as `teacher` → redirected to `/teach`
     - Dashboard: today's classes, attendance pending, homework, exams, announcements, subjects
     - View assigned classes & subjects, student lists, class timetable
     - Mark attendance (`/attendance/teacher`), upload homework, enter exam marks
     - Post class announcements, view homework submissions

14. For Student Portal (Module 10), run:
   ```
   sql/module10_student_portal.sql
   ```

   Prerequisites: enable student login via **Students → View Student → Enable Student Login**.

   - **Students:** log in as `student` → redirected to `/learn`
     - Dashboard: schedule, attendance, homework, results, exams, fees, announcements
     - Profile, daily/monthly attendance, class timetable, subjects
     - View & submit homework, exam results with grade summary
     - Fee status, study materials, notifications, messages to school

15. For Exam & Result Management (Module 11), run:
   ```
   sql/module11_exam_results.sql
   ```
   Also install PDF support: `pip install fpdf2`

   - **Admin:** **Exams & Results** in sidebar or `/exams`
     - Create exam terms (Monthly Test, Midterm, Final)
     - Add subjects with max marks, pass marks, weight %
     - Teachers enter subject-wise marks per class
     - Calculate totals, percentages, grades, class ranks
     - Generate result cards, download PDF, publish results
     - Notify parents when results are shared
   - **Teachers:** `/exams` — enter marks for assigned classes
   - **Students/Parents:** published results appear in `/learn/results` and `/portal/results`

16. For Homework / Classwork Management (Module 12), run:
   ```
   sql/module12_homework.sql
   ```
   Create a **Storage** bucket named `homework-attachments` (public) in Supabase Dashboard → Storage.

   - **Teachers:** `/teach/homework`
     - Upload homework or classwork with title, description, attachment, class/section, subject, due date
     - View homework history, submissions, who has seen assignments, and add teacher comments
   - **Students:** `/learn/homework`
     - View assignments, download attachments, mark as seen (automatic on open), submit online when enabled
   - **Parents:** `/portal/homework`
     - View children's homework, download attachments, see due dates and submission status (parent visibility)
