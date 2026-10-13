# Kelsey Trimming — customer portal

Customers sign up → grouped by area (from zip) → Kelsey plans a **Trip** (area + dates):

1. **Send projected dates** — heads-up email to everyone in the area; each is marked notified.
2. **Send firm dates** — email with a personal link to a confirm page (pre-filled, like the sign-up page).
3. **Confirmed** — the trip page lists who confirmed with phone, animals and visit notes. That's the route sheet.

Re-pressing a send button only emails people who haven't had it yet (new sign-ups), never confirmed/declined people.
People who confirm by text/phone get marked with the Confirm button. The Trips list is the route history.

| Path | What |
|---|---|
| `/` | public sign-up |
| `/confirm/<token>` | public confirm page from the firm-dates email |
| `/admin/` | Trips: plan a trip, open one to send emails and see confirmed |
| `/admin/customer/`, `/admin/area/` | plain CRUD; editing a zip or an area regroups customers |

Code: `models.py` (Customer, Area, Trip, Stop), `trips.py` (send steps, email text), `views.py` (public pages),
`admin.py` (Flask-Admin views), `emailer.py` (one SMTP connection per batch).

## Local dev
```bash
docker compose -f docker-compose.dev.yml up --build -d
docker compose -f docker-compose.dev.yml exec web flask seed-demo   # 50 fake customers
```
Portal http://localhost:5001/admin (kelsey / demo) · caught emails http://localhost:8025 (Mailpit)

Tests: `venv/bin/python -m pytest -q`

## Deploy
```bash
cp .env.example .env   # secret key + Kelsey's Gmail + App Password
docker compose up -d --build
docker compose exec web flask create-user kelsey
```
HTTPS via nginx/Cloudflare in front (ProxyFix is on so confirm links come out https). Back up `./instance/`.

## Notes
- Gmail App Password needs 2-Step Verification on her account. Free Gmail ≈ 500 recipients/day over SMTP.
- WTForms pinned to 3.0.1: Flask-Admin 1.6.1 select fields break on WTForms ≥ 3.1.
- No migrations yet (`db.create_all()`); add Flask-Migrate before changing models on a live DB.
