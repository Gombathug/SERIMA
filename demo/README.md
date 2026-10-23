# SERIMA — local case management demo ("AI Act - Demo")

Local-only demo of SERIMA running its **case management** module (`cases/`) in
place of Incident Notification: a regulator builds forms (questions + order),
people submit cases (questions, complaints, information requests) through them,
and the regulator reviews each case until it closes it.

It is the real code of this repository, run with `DEBUG = True` against a local
PostgreSQL, on top of the documentation's screenshot data
(`docs/screenshots/fixture.json`). Security Objectives and Reporting are off.

**For testing and demonstration only.** The passwords below are public, 2FA is
skipped (`DEBUG = True`), and emails are written to files instead of being sent.

## Accounts

Every account uses the password `SerimaDemo2026!` (change it with
`reset_demo.ps1 -Password ...`). Login is case-insensitive on the email.

| Email | Role | Belongs to | In the demo |
| --- | --- | --- | --- |
| `platformadmin@bipt.be` | Platform administrator | — | `/admin` only: regulators, regulations, users, functionalities |
| `RegAdmin@bipt.be` | Regulator administrator | IBPT | `/admin` › Case management: builds the forms and their questions |
| `RegUser@bipt.be` | Regulator user | IBPT | processes the cases sent to IBPT |
| `NewUser@bipt.be` | Incident user (no organisation) | — | submits cases, answers revision requests |
| `OpAdmin@bipt.be` | Operator administrator | Operator A and Operator B (picks one at login) | can submit cases on behalf of its operator |
| `OpUser@bipt.be` | Operator user | Operator B | can submit cases on behalf of its operator |

`NewUser@bipt.be` has the platform's `IncidentUser` role: the role SERIMA gives
anybody who signs up without an organisation ("Créer un compte" / "sans compte").
New sign-ups can therefore submit cases straight away.

Regulators: **IBPT** (L'Institut belge des services postaux et des
télécommunications), responsible for the regulation **AI Act - Demo**, and
**Regulator B**, whose accounts exist as data but cannot log in.

Starting data: one form, *Formulaire test*, with two questions (*Type de demande*:
Question / Plainte / Information, and *Description de votre demande*). No case.

## Demo scenario

1. **RegAdmin builds a complaint form** — log in as `RegAdmin@bipt.be`, open
   *Paramètres* (`/admin`) › *Gestion de dossiers*:
   - *Questions* › *Ajouter*: type (texte libre, choix unique, choix multiple,
     date), libellé, info-bulle, and the predefined answers for choice questions;
   - *Formulaires* › *Ajouter*: name, description, regulation *AI Act - Demo*,
     *Actif*, then add the questions with their position and *Obligatoire*.
2. **NewUser submits a complaint** — log in as `NewUser@bipt.be`, *AI Act - Demo* ›
   *Introduire un dossier*, pick the form, answer, optionally attach a file, send.
   The case gets a reference (`CA_…`) and the status *Revue en cours*. NewUser can
   then only wait: there is no comment box until the regulator gives feedback.
3. **RegUser reviews it** — log in as `RegUser@bipt.be`, *AI Act - Demo* › *Traiter*:
   read the submitted form and decide, with an optional file:
   - *Améliorations requises* (revision required) — the comment is mandatory and
     says what is missing. NewUser can now answer once, with a comment and a file;
     the answer sends the case back to *Revue en cours* for a new review.
   - *Clôturé* (closed) — final: nobody can add anything any more.
4. **History** — the *Historique* button on the case lists every iteration: the
   submission or answer of NewUser, and the decision of the regulator on it.

The review cycle:

```
Submission ──> Revue en cours ──> RegUser decides ──┬──> Clôturé (final)
                     ^                              │
                     └──── NewUser answers <── Améliorations requises
```

Each step sends an email (acknowledgement and decisions to the submitter,
submissions and answers to `notification@bipt.be`): see `sent_emails/`.

## Daily use

```powershell
powershell -ExecutionPolicy Bypass -File demo\start_demo.ps1   # http://127.0.0.1:8000
powershell -ExecutionPolicy Bypass -File demo\stop_demo.ps1    # stop PostgreSQL
powershell -ExecutionPolicy Bypass -File demo\reset_demo.ps1   # wipe and reload the demo data (after a code change too)
```

Sent emails land in `sent_emails/`, one `.log` file per message. Application logs
go to `logs/`, attachments to `tmp/cases/` (never served statically).

## How the module is switched on

Two optional settings in `governanceplatform/config.py`:

```python
BASE_MODULES = ["cases"]  # default ["incidents"]; ["incidents", "cases"] shows both
CASES_MODULE_NAME = "AI Act - Demo"  # name in the menu; default "Case management"
```

A module left out of `BASE_MODULES` disappears from the menus and the admin, and
its URLs answer 404. Incident Notification is still there: put `"incidents"` back
to show it again.

## What is installed where

| Piece | Location | Why |
| --- | --- | --- |
| Python venv | `.venv/` | `pip install -r requirements.txt` (+ pytest, ruff) |
| Front-end packages | `node_modules/` (linked as `static/npm_components`) | `npm ci` |
| Theme (templates, CSS, images) | `theme/` — IBPT `serimabe-theme`, release v0.6.0 (commit `7672c55`) | all rendered pages come from here |
| Config | `governanceplatform/config.py` (gitignored) | copy of `config_dev.py` with the local database |
| PostgreSQL 18 (portable) | `..\pgsql`, data in `..\pgdata` | the code uses PostgreSQL-only queries |
| MSYS2 (Pango, gettext) | `..\msys64` | WeasyPrint PDF reports, translations |

The theme has two local, uncommitted edits so its login and home pages follow the
enabled module (`templates/registration/login.html`, `templates/home/index.html`).

## Switching theme

`theme/` is one git clone with both themes as remotes: `serimabe-theme` (IBPT
look, used here) and `origin` (the neutral default theme of the documentation
screenshots). Both tag their release `v0.6.0`, so check out by commit; set the two
local edits aside first, then restart the server.

```powershell
git -C theme stash                                                # keep the two local edits
git -C theme checkout 0b3dfd62dd2fcb1edd5096c44d79420c963646ec   # default theme v0.6.0
git -C theme checkout 7672c556830ed2b22dddd62ccdd08772b9783e89   # back to IBPT
git -C theme stash pop                                            # reapply the edits
```

`SITE_NAME` in `governanceplatform/config.py` is `NISINP`, the name IBPT shows
in tab and admin titles.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest cases/tests --no-cov
```

The other apps' tests expect Incident Notification on: run them with
`BASE_MODULES` removed from `config.py`.

## Adapting it for another site

- **Branding / layout**: everything visible lives in `theme/`.
- **Organisation name, contact, site name**: `REGULATOR_CONTACT` and `SITE_NAME` in
  `governanceplatform/config.py`; module name: `CASES_MODULE_NAME`.
- **Forms and questions**: through `/admin` as RegAdmin, no code change needed.
- **Demo data and accounts**: `demo/setup_demo.py`.
