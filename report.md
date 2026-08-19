# Secure Login System — Project Report

**Task:** Secure Login System with User Details & File Access  
**Submitted by:** Lakshya Soni
**Date:** 19 August 2026

---

## 1. What I Built

The goal was to build a login/registration/logout system twice — once with a custom backend and once with a managed service (Appwrite). Both implementations share the same front-end test client (`index.html`) and must support:

- User registration (email + password)
- Login with session tokens (JWT for Django, Appwrite sessions for Appwrite)
- Logout with server-side session invalidation
- Protected user profile (`GET /me`)
- File listing (`GET /files`) — only the logged-in user's files
- Single file access (`GET /files/:id`) — must reject access to another user's files with a distinct 403 (not a generic 404)
- At least 3 seeded test users with their own files

---

## 2. Custom Backend: Django + DRF + JWT

### Tech Stack

- **Django 4.2** with **Django REST Framework**
- **SQLite** for development (PostgreSQL-ready via `DATABASE_URL`)
- **djangorestframework-simplejwt** for token management
- **argon2-cffi** for password hashing
- **django-cors-headers** for cross-origin requests

### Why JWT over Session Cookies

I went with JWT because:

1. **Stateless verification** — the server doesn't need to look up sessions in a database for every request (the token itself proves who you are)
2. **Works well with SPAs** — the front-end test client is a single HTML file that communicates via fetch, and JWT fits naturally with the `Authorization: Bearer` pattern
3. **Scalability** — if this were deployed across multiple servers, JWT works without shared session storage

### How Logout Works

When a user logs out, two things happen:

1. The **access token's jti** (a unique identifier inside the JWT) gets added to a `BlacklistedAccessToken` table. Every subsequent request checks this blacklist — if the jti is there, the request is rejected even though the JWT is technically still valid.

2. The **refresh token** is consumed from the database. Each refresh token is single-use — once it's been exchanged or deleted, it can't be reused.

This means even if someone stole the JWT, logging out immediately makes it useless.

### How User Data Isolation Works

- `GET /me` returns `request.user` — the user object from the JWT, not from any URL parameter. There's no way to supply a different user ID and get their data.
- `GET /files` filters `UserFile.objects.filter(user=request.user)`. Same principle — the user comes from the token, not the request body.
- `GET /files/:id` fetches the file and then checks `file.user_id != request.user.id`. If it doesn't match, it returns 403 (forbidden), which is distinct from 404 (not found). This is important — the task specifically requires that you can tell the difference between "file doesn't exist" and "file exists but isn't yours."

### Rate Limiting

- Failed login attempts are tracked per email + IP combination
- After 5 consecutive failures, the account is locked out for 15 minutes
- All error responses are identical ("Invalid email or password") — never reveals whether the email is registered

### Seed Script

```bash
python manage.py seed_demo
```

Creates:
- alice@example.com / Password123!
- bob@example.com / Password123!
- carol@example.com / Password123!

Each user gets 2 sample files with simple IDs (1-6).

### Setup

```bash
cd custom-backend
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 8001
```

---

## 3. Appwrite Backend

### What Appwrite Handles Automatically

A lot of the heavy lifting:

- **Password hashing** — Argon2 by default, no config needed
- **Session management** — creating, storing, and expiring sessions
- **User management** — registration, email/password login, account deletion
- **Rate limiting** — built into Appwrite Cloud
- **CORS** — handled through the Web Platform configuration

### What I Configured

- **Web Platform** — had to add `localhost` as a hostname in the Appwrite console so the browser SDK could talk to the API
- **Database collection** — created a `files` collection with attributes: `ownerId` (string), `name` (string), `des` (string), `size` (string)
- **Collection permissions** — set Read/Write/Create/Delete to `users` (authenticated users only)
- **Index on ownerId** — for efficient filtering of files per user
- **Storage bucket** — set up for file uploads (though the current demo uses metadata only)

### How the Adapter Works

The `appwrite-adapter.js` file intercepts `window.fetch` calls when Appwrite mode is selected. It routes each request to the appropriate Appwrite REST API endpoint:

| Client Request | Appwrite API Call |
|---|---|
| `POST /register` | `POST /v1/account` |
| `POST /login` | `POST /v1/account/sessions` |
| `POST /logout` | `DELETE /v1/account/sessions/current` |
| `GET /me` | `GET /v1/account` |
| `GET /files` | `GET /v1/databases/.../documents` with `ownerId` filter |
| `GET /files/:id` | `GET /v1/databases/.../documents/:id` with ownership check |

The adapter also auto-seeds 2 files per user after their first login, so you don't need to manually create test data.

### Key Bug I Fixed

The adapter was calling `fetch()` for Appwrite API calls, but `window.fetch` had already been patched by `mock-api.js`. This meant Appwrite requests were being intercepted by the mock layer, which returned "No route" errors. The fix was to save a reference to the original browser fetch before any patches:

```javascript
window.__nativeFetch = window.fetch.bind(window);
```

Then use `nativeFetch` for all Appwrite API calls.

---

## 4. Differences Between the Two Implementations

| Aspect | Django | Appwrite |
|---|---|---|
| Auth mechanism | JWT (stateless tokens) | Appwrite sessions (server-managed) |
| Password hashing | Argon2 (configurable) | Argon2 (automatic) |
| Data isolation | Manual filter in Django views | Query filter in Appwrite API + ownership check |
| Session invalidation | Blacklist jti + consume refresh token | Delete session server-side |
| Rate limiting | Custom (FailedLoginAttempt model) | Built into Appwrite Cloud |
| Database | SQLite/PostgreSQL | Appwrite Cloud database |
| Setup complexity | Higher (migrations, env vars) | Lower (console config) |
| Deployment | Self-hosted | Managed service |

---

## 5. What I Would Improve With More Time

- **Email verification** — currently disabled for testing, but should be required in production
- **Password strength validation** — the register endpoint only checks for non-empty passwords
- **CSRF protection** — JWT bypasses CSRF by design, but would add it for cookie-based auth
- **File storage** — right now files are metadata only (name, size, type). Would add actual file upload/download with Appwrite Storage
- **Logging** — add structured logging for security events (failed logins, token refreshes)
- **HTTPS** — the demo runs on HTTP localhost. Production would need TLS
- **Input sanitization** — add more thorough validation on email format, password complexity
- **Refresh token rotation** — the Django implementation already does single-use refresh tokens, but would add a refresh token family system to detect token reuse attacks

---

## 6. Running the Project

### Custom Backend

```bash
cd custom-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 8001
```

Then open `web/index.html`, select "Custom REST backend", set base URL to `http://localhost:8001`.

### Appwrite Backend

1. Create an Appwrite Cloud project
2. Add Web Platform with hostname `localhost`
3. Create a database and `files` collection with attributes: `ownerId` (string), `name` (string), `des` (string), `size` (string)
4. Set all collection permissions (Read/Write/Create/Delete) to `users`
5. Add index on `ownerId`
6. Open `web/index.html`, select "Appwrite", fill in your project settings
7. Register 3 users, login, and test

### Test Users

| Email | Password |
|---|---|
| alice@example.com | Password123! |
| bob@example.com | Password123! |
| carol@example.com | Password123! |

---

## 7. Files in the Repository

```
├── README.md                          # Setup instructions and documentation
├── report.md                          # This report
├── web/
│   ├── index.html                     # The required test client (all 3 modes)
│   ├── mock-api.js                    # In-browser mock backend (demo only)
│   ├── seed-data.json                 # Sample data for mock mode
│   └── appwrite-adapter.js           # Appwrite backend implementation
├── custom-backend/
│   ├── manage.py                      # Django entry point
│   ├── requirements.txt               # Python dependencies
│   ├── .env.example                   # Environment variables template
│   ├── config/
│   │   ├── settings.py               # Django configuration
│   │   ├── urls.py                   # Root URL router
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── users/
│   │   ├── models.py                 # User, RefreshSession, BlacklistedAccessToken, FailedLoginAttempt
│   │   ├── views.py                  # Register, Login, Logout, Refresh, Me
│   │   ├── serializers.py            # Input/output validation
│   │   ├── authentication.py         # Custom JWT auth with blacklist check
│   │   ├── tokens.py                 # Token pair issuance
│   │   ├── throttle.py               # Rate limiting logic
│   │   ├── urls.py                   # User endpoint routes
│   │   ├── admin.py
│   │   └── management/commands/seed_demo.py
│   └── files/
│       ├── models.py                 # UserFile model (ownership link)
│       ├── views.py                  # File list + detail with ownership enforcement
│       ├── serializers.py
│       └── urls.py
```
