# SERIMA — local Incident Notification demo

Local-only demo of SERIMA's Incident Notification module: the real code of this
repository, run with `DEBUG = True` against a local PostgreSQL, filled with the
documentation's screenshot data (`docs/screenshots/fixture.json`). The Security
Objectives and Reporting modules are switched off.

**For testing and demonstration only.** The passwords below are public, 2FA is
skipped (`DEBUG = True`), and emails are written to files instead of being sent.

## Accounts

Every account uses the password `SerimaDemo2026!` (change it with
`reset_demo.ps1 -Password ...`). Login is case-insensitive on the email.

| Email | Role | Belongs to | Main screens |
| --- | --- | --- | --- |
| `platformadmin@bipt.be` | Platform administrator | — | `/admin` only: regulators, regulations, observers, entity categories, users, functionalities |
| `RegAdmin@bipt.be` | Regulator administrator | Regulator A | incidents, review reports; `/admin`: sectors, operators, users, and the incident form (workflows, questions, impacts, emails, sector regulations) |
| `RegUser@bipt.be` | Regulator user | Regulator A (sector Energy › Electricity) | incidents of its sector, review reports |
| `OpAdmin@bipt.be` | Operator administrator | Operator A and Operator B (picks one at login) | declare incidents, fill in reports; `/admin`: its company's users |
| `OpUser@bipt.be` | Operator user | Operator B | declare incidents, fill in reports |

The platform administrator cannot edit workflows or questions: in SERIMA the
incident form belongs to each regulator, so that is the regulator administrator's job.

The fixture also holds Regulator B, an observer and an incident user. Their
accounts exist as data (they own sample incidents and logs) but cannot log in.

## Daily use

```powershell
powershell -ExecutionPolicy Bypass -File demo\start_demo.ps1   # http://127.0.0.1:8000
powershell -ExecutionPolicy Bypass -File demo\stop_demo.ps1    # stop PostgreSQL
powershell -ExecutionPolicy Bypass -File demo\reset_demo.ps1   # wipe and reload the demo data
```

Sent emails (notification acknowledgements, password resets…) land in
`sent_emails/`, one `.log` file per message. Application logs go to `logs/`.

## What is installed where

| Piece | Location | Why |
| --- | --- | --- |
| Python venv | `.venv/` | `pip install -r requirements.txt` |
| Front-end packages | `node_modules/` (linked as `static/npm_components`) | `npm ci` |
| Theme (templates, CSS, images) | `theme/` — IBPT `serimabe-theme`, release v0.6.0 (commit `7672c55`) | all rendered pages come from here |
| Config | `governanceplatform/config.py` (gitignored) | copy of `config_dev.py` with the local database |
| PostgreSQL 18 (portable) | `..\pgsql`, data in `..\pgdata` | the code uses PostgreSQL-only queries |
| MSYS2 (Pango, gettext) | `..\msys64` | WeasyPrint PDF reports, translations |

No Redis/Celery worker runs: the incident module does not use them. The
scheduled deadline reminders (`celery_beat.py`) are therefore not sent; run
`python manage.py check_incident` by hand to trigger them.

## Switching theme

`theme/` is one git clone with both themes as remotes: `serimabe-theme` (IBPT
look, used here) and `origin` (the neutral default theme of the documentation
screenshots). Both tag their release `v0.6.0`, so check out by commit; then
restart the server.

```powershell
git -C theme checkout 7672c556830ed2b22dddd62ccdd08772b9783e89   # IBPT (serimabe-theme v0.6.0)
git -C theme checkout 0b3dfd62dd2fcb1edd5096c44d79420c963646ec   # default theme v0.6.0
```

`SITE_NAME` in `governanceplatform/config.py` is `NISINP`, the name IBPT shows
in tab and admin titles.

## Adapting it for another site

- **Branding / layout**: everything visible lives in `theme/` (`templates/`, `static/`,
  `globals.py`). Fork the theme rather than editing `templates/` in this repo.
- **Organisation name, contact, site name**: `REGULATOR_CONTACT` and `SITE_NAME` in
  `governanceplatform/config.py`.
- **Workflows, questions, impacts, emails, sectors**: through `/admin`, no code change
  needed. Export/import them with `manage.py export_sector_regulation` / `import_sector_regulation`.
- **Demo accounts**: `ACCOUNTS` in `demo/setup_demo.py`.
