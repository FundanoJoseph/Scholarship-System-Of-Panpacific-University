# Deploying to Render

`render.yaml` in the repository root describes one web service that serves both
the pages and the API, so a deploy gives you a working site at
`https://<service-name>.onrender.com`.

## 1. Fast demo deploy (bundled SQLite database)

1. Push this branch to GitHub (already done if you are reading this from the repo).
2. Open <https://dashboard.render.com> -> **New** -> **Blueprint**.
3. Pick `FundanoJoseph/Scholarship-System-Of-Panpacific-University` and the branch
   you want to deploy, then **Apply**. Render reads `render.yaml` and asks for
   nothing else: `JWT_SECRET` is generated for you.
4. Wait for the build, then open the service URL. The first start creates the
   database schema and the demo accounts automatically.

Sign in with:

| Role | Email | Password |
| --- | --- | --- |
| Admin | admin@panpacificu.edu.ph | `Panpacific#2026` |
| Staff | staff@panpacificu.edu.ph | `Panpacific#2026` |
| Student | juan.delacruz@panpacificu.edu.ph | `Panpacific#2026` |
| Student | ana.reyes@panpacificu.edu.ph | `Panpacific#2026` |

**Free plan limits to know about**

- The service sleeps after ~15 minutes idle and takes about a minute to wake up.
- The filesystem is temporary. Every redeploy and every restart wipes the SQLite
  database and the uploaded documents, and the demo data is created again on the
  next start. Anything you enter is for demonstration only.
- For data that survives restarts, use Supabase (step 2) - it is free and takes
  about five minutes.

If you prefer to wire the service up by hand instead of using the blueprint:
**New -> Web Service**, Root Directory `backend`, Build Command
`pip install -r requirements.txt`, Start Command
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`, Health Check Path
`/api/health`, Python version `3.12.7`, and set the environment variables listed
at the bottom of this file.

## 2. Recommended: keep the data in Supabase

Do this before a real demo so accounts, applications and documents survive.

1. Create a Supabase project and run `supabase/schema.sql` in the SQL editor.
2. In Render, open the service -> **Environment** and add:

   | Key | Value |
   | --- | --- |
   | `AUTH_PROVIDER` | `supabase` |
   | `STORAGE_BACKEND` | `supabase` |
   | `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
   | `SUPABASE_ANON_KEY` | publishable / anon key |
   | `SUPABASE_SERVICE_KEY` | secret / service_role key |
   | `DATABASE_URL` | Session pooler connection string, ending with `?sslmode=require` |
   | `PASSWORD_RESET_REDIRECT` | `https://<your-service>.onrender.com/template/reset-password.html` |
   | `SEED_DEMO_ACCOUNTS` | `false` |

   Remove the `SEED_DEMO_ACCOUNTS=true` value that the blueprint set, because
   Supabase Auth owns the accounts.
3. In Supabase, **Authentication -> URL configuration**, set the site URL to your
   Render URL and add the reset redirect above.
4. Save. Render redeploys and the site now runs on Supabase.

### Create yourself an admin (no demo accounts)

1. Register through the app - that always creates a student.
2. Give that account the admin role, either in the Supabase SQL editor:

   ```sql
   update public.users set role = 'admin' where lower(email) = lower('you@panpacificu.edu.ph');
   ```

   or from the Render **Shell** of the service:

   ```sh
   python scripts/promote_admin.py you@panpacificu.edu.ph
   ```

3. Log in again. The Admin / Staff side appears, and further staff or admin
   accounts can be created from **Account Management** inside the app.

## 3. Handy Render commands

From the service **Shell** (the working directory is `backend/`):

```sh
python -m app.demo_seed                  # create the demo accounts and applications
python scripts/promote_admin.py --list   # list the accounts in the database
python scripts/promote_admin.py you@panpacificu.edu.ph
```

## Environment variables used by the blueprint

| Key | Value | Why |
| --- | --- | --- |
| `PYTHON_VERSION` | `3.12.7` | Render's default is newer; this keeps the same version the project was tested on |
| `ENVIRONMENT` | `production` | Turns off the development-only password reset token |
| `AUTH_PROVIDER` | `local` | Passwords hashed by this API. Switch to `supabase` for Supabase Auth |
| `STORAGE_BACKEND` | `local` | Documents on disk. Switch to `supabase` for the Storage bucket |
| `JWT_SECRET` | generated | Signing key for sessions in `local` mode |
| `SEED_DEMO_ACCOUNTS` | `true` | Creates the demo accounts only while the database is empty |
| `UNIVERSITY_EMAIL_DOMAIN` | `@panpacificu.edu.ph` | Registration and password reset only accept this domain |

Optional:

| Key | When |
| --- | --- |
| `PUBLIC_BASE_URL` | Only for custom domains; on Render the onrender.com address is detected automatically |
| `CORS_ORIGINS` | Only when the pages are hosted on a different origin than the API |
| `DATABASE_URL` | Postgres, including the Supabase pooler |
| `SUPABASE_*` | When Supabase Auth or Storage is used |
| `PASSWORD_RESET_REDIRECT` | Overrides the reset link target |

## Notes

- Health check: `GET /api/health` returns `{"status":"ok","database":true,...}`.
- The API publishes only `index.html`, `template/`, `css/`, `js/` and `assets/`.
  Backend sources, `supabase/` and any `.env` file are never served.
- Password reset by e-mail needs a mail provider. In `local` mode the API answers
  with a clear message instead of pretending to send one; with Supabase Auth the
  recovery e-mail is sent by Supabase.
- Uploads are limited to 5 MB per file (PDF, JPG, PNG). Change `MAX_UPLOAD_MB` if
  the scholarship office needs more.
