# Custom Backend (Django)

This folder contains the Django implementation of the login system.

## Tech Stack

- Django 4.2 + Django REST Framework
- SQLite (default) or PostgreSQL (set DATABASE_URL)
- JWT authentication (djangorestframework-simplejwt)
- Argon2 password hashing

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # optional
python manage.py migrate
python manage.py seed_demo       # creates 3 test users + files
python manage.py runserver 8001
```

## API endpoints

| Method | Route | Auth | Description |
|---|---|---|---|
| POST | /register | no | Create account |
| POST | /login | no | Login, returns JWT tokens |
| POST | /logout | yes | Invalidate session |
| POST | /refresh | no | Get new token pair |
| GET | /me | yes | Current user profile |
| GET | /files | yes | List user's files |
| GET | /files/:id | yes | Get single file (403 if not yours) |
| GET | /files/:id/download | yes | Download file |

## Key files

- `config/settings.py` — Django configuration
- `users/views.py` — Auth views (register, login, logout, me)
- `users/authentication.py` — Custom JWT auth with blacklist check
- `users/tokens.py` — Token pair issuance
- `users/throttle.py` — Rate limiting logic
- `files/views.py` — File views with ownership enforcement
- `users/management/commands/seed_demo.py` — Seed script

## Security features

- Passwords hashed with Argon2
- JWT access tokens (15 min) + refresh tokens (7 days)
- Refresh tokens stored as SHA-256 hashes (single-use)
- Blacklist on logout (access token jti)
- Rate limiting: 5 failed attempts → 15 min lockout
- Generic error messages (never reveals if email exists)
