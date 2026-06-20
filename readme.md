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
