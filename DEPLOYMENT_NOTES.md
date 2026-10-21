# CampusNet — Free deployment notes

This package is prepared for a demo deployment on Render.

## Important database note
This app currently uses SQLite. Render free web services have an ephemeral filesystem, so SQLite data can be lost when the service restarts, spins down, or redeploys. This package uses `/tmp/campusnet.db`, which lets the app initialize its database at startup, but it does NOT make saved data permanent. Use this deployment for a demo unless the database is migrated to a persistent external database.

## Render settings
- New > Blueprint (if you want to use `render.yaml`) OR create a Web Service from the GitHub repository.
- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Health check path: `/api/health`
- Choose the Free instance plan.
- If configuring manually, add environment variable `SECRET_KEY` with a long random value.
- Do not upload `.env` files, passwords, or API keys to GitHub.

## Before publishing
- Review demo/admin account setup and change any default credentials.
- Do not use this demo deployment for real campus network control or sensitive data.
