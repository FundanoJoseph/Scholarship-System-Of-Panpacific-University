# Panpacific University Scholarship System

Student scholarship portal for Panpacific University: student registration and
applications, Authorized Staff evaluation, and Admin account management.

## Repository structure

```text
.
├── index.html          # Redirects to template/index.html
├── template/           # HTML pages (login, registration, dashboards, etc.)
├── css/                # Stylesheets
├── js/                 # JavaScript files
├── backend/            # FastAPI app: sign-in, roles, business rules, file access
├── supabase/           # schema.sql - the database and storage setup
└── assets/
    ├── documents/      # Scholarship agreement PDFs
    └── images/         # University logo and other images
```

The pages live in `template/` and are served by the backend, so they are opened
over `http://` instead of `file://`, and `js/data.js` / `js/files.js` reach the
API with relative `/api/...` URLs.

## Run it

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000/>. The API serves the pages, CSS, JavaScript and
assets, so nothing else is needed. With no configuration it uses SQLite
(`backend/var/dev.db`), keeps uploaded documents on local disk, and handles
sign-in itself with bcrypt-hashed passwords and JWT sessions.

Useful extras while developing:

```sh
python scripts/seed_dev.py            # sample accounts and applications
python scripts/promote_admin.py --list
python scripts/promote_admin.py you@panpacificu.edu.ph
```

## Moving to Supabase

Supabase owns the Postgres database and the Storage bucket for uploaded
documents. FastAPI owns sign-in, roles and the business rules, and the browser
never talks to Supabase directly.

1. Create a Supabase project, then run `supabase/schema.sql` in the SQL editor.
2. Copy `backend/.env.example` to `backend/.env` and fill in the Supabase values
   (see `backend/README.md` for the full list).
3. Restart the API.

There is no pre-made admin account by design: register normally through the app
(that always creates a student), then promote the account with
`python scripts/promote_admin.py you@panpacificu.edu.ph` or one SQL `UPDATE`.
After that, further staff and admin accounts are created inside the app's
**Account Management** page.

## Frontend notes

- `js/data.js` is the only file that calls the API for data, and `js/files.js`
  is the only one that fetches uploaded documents. Everything else is unchanged.
- Old browser-only data (`localStorage` key `sams_db_v3`, the `sams_files_v2`
  IndexedDB database and the old session keys) is cleared automatically the
  first time a page loads, and is no longer used.
- Passwords never reach the browser: they are hashed by Supabase Auth or, in
  local mode, by the backend with bcrypt.
- To point the pages at an API on another host, set
  `<script>window.SAMS_API_BASE = "https://your-api.example.com/api";</script>`
  or a `<meta name="sams-api-base" content="...">` tag before the other scripts,
  and add that origin to `CORS_ORIGINS` on the server.
