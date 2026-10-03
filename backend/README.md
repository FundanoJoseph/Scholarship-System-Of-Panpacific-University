# Scholarship System API (FastAPI + Supabase)

This folder replaces the old browser-only data layer. `js/data.js` and `js/files.js`
no longer read `localStorage` or IndexedDB - they call this API, and the API is the
only thing that talks to the database and to file storage.

## How the pieces fit

| Concern | Owner |
| --- | --- |
| Sign-in, sessions, roles | Supabase Auth (`AUTH_PROVIDER=supabase`) or this API (`AUTH_PROVIDER=local`) |
| Business rules (who may evaluate, valid status changes, term rollover, notifications) | FastAPI |
| Application data | Supabase Postgres |
| Uploaded documents | Supabase Storage (or local disk while developing) |

The browser never talks to Supabase directly. It only calls this API, so the rules
live in one place and the Supabase Row Level Security policies stay locked down
(`supabase/schema.sql` enables RLS and revokes `anon` / `authenticated` access).
Any request without a valid token is rejected.

Soft deletes: rows carry `deleted_at`. "Active" queries filter
`deleted_at IS NULL`; the status history / audit query does not filter it at all,
so what happened is never hidden.

## Run it locally (no Supabase project needed)

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000/> - the API also serves the pages, CSS, JavaScript and
assets, so there is no CORS setup and no file:// problems. Defaults without a
`.env`: SQLite database at `backend/var/dev.db`, documents on local disk,
sign-in handled by this API with bcrypt-hashed passwords and JWTs.

Optional extras:

```sh
python scripts/seed_dev.py           # sample accounts and applications
python scripts/promote_admin.py --list
python scripts/promote_admin.py you@panpacificu.edu.ph
```

`seed_dev.py` signs in through the same endpoints the browser uses and prints the
accounts it created.

## Point it at Supabase

1. **Create the project**, then open **SQL Editor** and run the whole of
   [`../supabase/schema.sql`](../supabase/schema.sql). That creates the tables,
   indexes, triggers, the private `scholarship-documents` bucket and the locked
   down RLS policies.
2. **Copy `backend/.env.example` to `backend/.env`** and fill in:
   - `AUTH_PROVIDER=supabase`
   - `STORAGE_BACKEND=supabase`
   - `SUPABASE_URL=https://<project-ref>.supabase.co`
   - `SUPABASE_ANON_KEY=` the publishable / anon key
   - `SUPABASE_SERVICE_KEY=` the secret / service_role key (server only, never in the browser)
   - `DATABASE_URL=` the **Session pooler** connection string from
     *Project settings -> Database*, with `?sslmode=require` at the end
   - `PASSWORD_RESET_REDIRECT=https://your-site/template/reset-password.html`
   - `JWT_SECRET=` any long random value
3. In **Authentication -> URL configuration**, add your site URL and the
   `.../template/reset-password.html` redirect so the recovery e-mail can come back
   to the app.
4. Restart the API. Passwords and sessions are now handled by Supabase Auth: this
   API verifies the access token Supabase issues (JWKS for modern asymmetric keys,
   the shared secret or `GET /auth/v1/user` for older projects) and then applies the
   role stored in `public.users`.

Keep `SUPABASE_SERVICE_KEY` on the server. It bypasses RLS, which is fine here
because nothing else can reach the database.

## Deploying

`render.yaml` at the repository root deploys this API (and the pages it serves)
to Render in one step. [../RENDER.md](../RENDER.md) walks through both the quick
SQLite demo deploy and the Supabase-backed setup.

## First administrator

There is deliberately no built-in admin account.

1. Register normally through the app (`template/register.html`) - always a student.
2. Promote that account:

   ```sh
   python scripts/promote_admin.py you@panpacificu.edu.ph
   ```

   or run this once in the Supabase SQL editor:

   ```sql
   update public.users set role = 'admin' where lower(email) = lower('you@panpacificu.edu.ph');
   ```

3. Log in again. The Admin / Staff side appears, and every other staff or admin
   account can be created from **Account Management** inside the app.

## Environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | In development the password reset endpoint returns a reset token instead of e-mailing it |
| `AUTH_PROVIDER` | `local` | `local` or `supabase` |
| `JWT_SECRET` | dev value | Change it. Used for the tokens this API issues in `local` mode |
| `ACCESS_TOKEN_MINUTES` | `480` | |
| `REFRESH_TOKEN_DAYS` | `14` | |
| `DATABASE_URL` | `sqlite:///./var/dev.db` | Any Postgres URL works, including the Supabase pooler |
| `STORAGE_BACKEND` | `local` | `local` or `supabase` |
| `STORAGE_BUCKET` | `scholarship-documents` | |
| `UPLOAD_DIR` | `./var/uploads` | Used by the local storage backend |
| `MAX_UPLOAD_MB` | `5` | PDF, JPG or PNG only |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_KEY` | empty | Needed when `AUTH_PROVIDER=supabase` or `STORAGE_BACKEND=supabase` |
| `SUPABASE_JWT_SECRET` | empty | Only for projects still using the legacy HS256 signing keys |
| `PASSWORD_RESET_REDIRECT` | empty | Where the Supabase recovery e-mail should return to |
| `UNIVERSITY_EMAIL_DOMAIN` | `@panpacificu.edu.ph` | Registration and password reset only accept this domain |
| `CORS_ORIGINS` | localhost origins | Comma separated list, only needed when the frontend is hosted separately |
| `SERVE_FRONTEND` / `FRONTEND_DIR` | `true` / `..` | Serve the pages from this API. Only `index.html`, `template/`, `css/`, `js/` and `assets/` are published |
| `PUBLIC_BASE_URL` | empty | Public address of the API. On Render the onrender.com hostname is detected automatically |
| `SEED_DEMO_ACCOUNTS` | `false` | Creates the demo accounts and applications when the database is still empty. Development and demos only |

## Hosting the frontend elsewhere

If the pages are hosted on a different origin (GitHub Pages, Netlify, ...) point
them at the API before the other scripts load, either with a global:

```html
<script>window.SAMS_API_BASE = "https://your-api.example.com/api";</script>
```

or a meta tag: `<meta name="sams-api-base" content="https://your-api.example.com/api">`.
Then add that origin to `CORS_ORIGINS` on the server.

## Endpoints

| Method | Path | Who |
| --- | --- | --- |
| POST | `/api/auth/register` | anyone (students only) |
| POST | `/api/auth/login` | anyone |
| POST | `/api/auth/refresh` | anyone with a refresh token |
| POST | `/api/auth/logout` | signed in |
| GET | `/api/auth/me` | signed in |
| POST | `/api/auth/password-reset/request` | anyone |
| POST | `/api/auth/password-reset/confirm` | anyone with a reset token |
| POST | `/api/auth/change-password` | signed in |
| GET / POST | `/api/term` | signed in / staff and admin |
| GET / POST | `/api/users` | admin (list and create staff or admin accounts) |
| PATCH | `/api/users/me` | signed in |
| GET | `/api/applications?scope=active\|all\|mine\|mine-active` | role aware |
| GET | `/api/applications/history` | staff and admin (audit trail, includes deleted applications) |
| GET | `/api/applications/{id}` | owner or staff |
| POST | `/api/applications` | students (multipart: `payload` + one file per requirement) |
| POST | `/api/applications/{id}/status` | staff and admin |
| PATCH | `/api/applications/{id}/discount` | staff and admin |
| DELETE | `/api/applications/{id}` | staff and admin (soft delete) |
| GET / POST | `/api/applications/{id}/documents/{requirement}` | owner or staff |
| GET | `/api/notifications`, `/api/notifications/unread-count` | signed in |
| POST | `/api/notifications/{id}/read`, `/api/notifications/read-all` | signed in |
| GET | `/api/health` | anyone |
| GET | `/api/docs` | interactive API documentation |

## Tests

```sh
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                          # API rules on a throw-away SQLite database
python scripts/verify_supabase_mode.py       # sign-in + storage through Supabase Auth/Storage
```

`pytest` runs against a throw-away SQLite database and local file storage, so it
never touches your development or Supabase data (13 tests).

`verify_supabase_mode.py` starts `scripts/mock_supabase.py`, a stand-in that
speaks the same Auth and Storage endpoints as Supabase, boots the API with
`AUTH_PROVIDER=supabase` and `STORAGE_BACKEND=supabase`, and walks through
registration, login, tokens, roles, document upload and download, password
changes, recovery e-mail hand-off and the audit trail. It covers both signing
styles: `rs256` with JWKS (new Supabase projects) and `hs256` with the legacy
shared secret. GitHub Actions runs both on every push
(`.github/workflows/tests.yml`).
