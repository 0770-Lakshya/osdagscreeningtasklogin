# Custom Backend (Django)

This is the Django implementation of the login system.

## Tech Stack

- Django 6.1 + Django REST Framework
- SQLite (default) or PostgreSQL (set `DATABASE_URL` in `.env`)
- JWT authentication via djangorestframework-simplejwt
- Argon2 password hashing

## Quick start

```bash
cd custom-backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # optional — SQLite works without it
python manage.py migrate
python manage.py seed_demo       # creates 3 test users + files
python manage.py runserver 8001
```

## Running tests

```bash
python manage.py test
```

28 tests across two files:

**users/tests.py (12 tests):**
- Registration creates a user and returns tokens
- Duplicate email is rejected
- Short password is rejected
- Login works with correct credentials
- Wrong password returns 401
- Wrong email returns 401
- Both cases return the same error message (no info leakage)
- Account locks out after 5 failed attempts
- GET /me works when authenticated
- GET /me without token returns 401
- Logout works
- Token is dead after logout

**files/tests.py (16 tests):**
- User sees only their own files
- Accessing someone else's file returns 403, not 404
- Nonexistent file returns 404
- Unauthenticated requests return 401
- With 5 users and 15 files, each user sees exactly 3
- Nobody can access anyone else's files
- Download endpoint also blocks cross-user access
- ID guessing doesn't work
- File list never leaks other users' emails

## API endpoints

| Method | Route | Auth | Description |
|---|---|---|---|
| POST | /register | no | Create account |
| POST | /login | no | Login, returns JWT tokens |
| POST | /logout | yes | Invalidate session (blacklists access token) |
| POST | /refresh | no | Exchange refresh token for a new pair |
| GET | /me | yes | Current user profile |
| GET | /files | yes | List user's files only |
| GET | /files/:id | yes | Get single file (403 if not yours, 404 if not found) |
| GET | /files/:id/download | yes | Download file bytes |

## Key files

- `config/settings.py` — Django config (DB, JWT, CORS, rate limits)
- `users/models.py` — User, RefreshSession, BlacklistedAccessToken, FailedLoginAttempt
- `users/views.py` — Auth views (register, login, logout, refresh, me)
- `users/authentication.py` — Custom JWT auth with blacklist check
- `users/tokens.py` — Token pair issuance
- `users/throttle.py` — Rate limiting logic
- `files/views.py` — File views with ownership enforcement
- `users/management/commands/seed_demo.py` — Seed script

## Security stuff

- Passwords hashed with Argon2
- JWT access tokens (15 min) + refresh tokens (7 days, single-use)
- Refresh tokens stored as SHA-256 hashes (never plaintext)
- Blacklist on logout (access token jti is rejected after logout)
- Rate limiting: 5 failed login attempts → 15 minute lockout
- Generic error messages (never reveals whether an email is registered)
- 403 vs 404 distinction: you can tell if a file doesn't exist vs if it exists but isn't yours
