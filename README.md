# Panpacific University Scholarship System

## Repository structure

```text
.
├── index.html          # Redirects to template/index.html
├── template/           # HTML pages (login, registration, dashboards, etc.)
├── css/                # Stylesheets
├── js/                 # JavaScript files
└── assets/
    ├── documents/      # Scholarship agreement PDFs
    └── images/         # University logo and other images
```

The application's HTML pages live in `template/`. Links between pages remain
relative to that folder. Stylesheets, scripts, and assets are referenced with
`../css/`, `../js/`, and `../assets/` so the site also works when hosted under a
subdirectory.

The root `index.html` is a small redirect that keeps the site's default entry
point working. Edit `template/index.html` to change the login page.

## Run locally

No build step is required. From the repository root, run:

```sh
python3 -m http.server 8000 --bind 0.0.0.0
```

Open `http://localhost:8000/` in your browser, or go directly to
`http://localhost:8000/template/index.html`. Serve the repository root, not just
`template/`, so the sibling CSS, JavaScript, and asset folders are accessible.
