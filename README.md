# Secure Login System

This is my submission for the FOSSEE Osdag Autumn Semester Internship 2026 — the **Login System with User Details & File Access** screening task.

I built the same login system twice:
- **Custom backend**: Django 6.1 + DRF + JWT (SQLite for dev, can switch to PostgreSQL)
- **Appwrite backend**: Appwrite Cloud, with a JS adapter in the browser

Both share the same frontend (`web/index.html`).

---

## Project structure

```
├── custom-backend/               # Django backend
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── config/                   # settings, urls, wsgi, asgi
│   ├── users/                    # register, login, logout, refresh, me
│   │   ├── tests.py              # 12 auth tests
│   │   └── management/commands/seed_demo.py
│   └── files/                    # file list, detail, download
│       └── tests.py              # 16 data isolation tests
│
├── appwrite-backend/             # Appwrite backend
│   └── appwrite-adapter.js       # adapter that talks to Appwrite REST API
│
├── web/                          # Shared test client
│   ├── index.html                # the required GUI (Mock / Custom / Appwrite modes)
│   ├── mock-api.js               # in-browser mock for quick demo
│   ├── seed-data.json            # mock seed data
│   └── README.md                 # how to run the web client
│
├── README.md
└── report.md
```

---

## Running the Django backend

```bash
cd custom-backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # optional, SQLite works fine without it
python manage.py migrate
python manage.py seed_demo       # makes 3 users + files
python manage.py runserver 8001
```

Then open `web/index.html`, select "Custom REST backend", and set Base URL to `http://localhost:8001`.

## Running the Appwrite backend

You need a free Appwrite Cloud account.

1. Go to [cloud.appwrite.io](https://cloud.appwrite.io) and create a project
2. Add a Web Platform — hostname should be `localhost`
3. Auth → Settings → make sure Email/Password auth is enabled
4. Create a database, then create a `files` collection with these attributes:
   - `ownerId` (string, 255, required)
   - `name` (string, 255, required)
   - `des` (string, 255)
   - `size` (integer)
5. Add an index on `ownerId`
6. Permissions — set Read, Write, Create, Delete all to `users`
7. In `web/index.html` pick the Appwrite radio, fill in your Endpoint, Project ID, Database ID, Collection ID, and Bucket ID (get these from the URLs in your Appwrite console — the endpoint needs the region prefix like `sfo.cloud.appwrite.io`)

Once that's done, register and login through the client. The adapter auto-creates sample files for each user.

---

## Test users

| Email | Password |
| alice@example.com | Password123! |
| bob@example.com | Password123! |
| carol@example.com | Password123! |

Each user gets 2 files. File IDs are simple numbers (1, 2, 3...):

| ID | File | Owner |
| 1 | resume_alice.pdf | alice |
| 2 | profile_photo.jpg | alice |
| 3 | project_notes.txt | bob |
| 4 | invoice_march.pdf | bob |
| 5 | test_plan.docx | carol |
| 6 | vacation.png | carol |

---

## Running tests

```bash
cd custom-backend
python manage.py test
```

28 tests total. They check things like: each user only sees their own files, accessing someone else's file gives 403 not 404, wrong password and wrong email both give the same error so you can't guess which emails exist, and the account locks out after 5 bad attempts.

---

## API endpoints

Both backends expose these routes:

| Method | Route | Auth | What it does |
| POST | `/register` | no | create account |
| POST | `/login` | no | login, returns tokens |
| POST | `/logout` | yes | invalidate session |
| POST | `/refresh` | no | get new token pair |
| GET | `/me` | yes | current user profile |
| GET | `/files` | yes | list user's files |
| GET | `/files/:id` | yes | get single file (403 if not yours) |
| GET | `/files/:id/download` | yes | download file |

---

## Why I made these choices

### JWT vs sessions

I went with JWT for Django because the server doesn't need to hit the database on every request to check who you are. But I do store refresh tokens server-side (hashed with SHA-256) so they can be revoked when you log out. Kind of a best-of-both-worlds thing.

Appwrite handles sessions on its own. The adapter just relies on httpOnly cookies — when you login, Appwrite sets a cookie, and the browser sends it automatically with every request via `credentials: "include"`.

### How logout works

For Django, when you logout the server does two things: deletes the refresh token from the database, and blacklists the access token's `jti`. So even if someone has a valid-looking token, it gets rejected after logout.

For Appwrite, the adapter sends `DELETE /v1/account/sessions/current` and Appwrite destroys the session on their end.

### Data isolation (the main security thing)

**Django:**
- `get_queryset()` filters by `owner=request.user` — you can't list someone else's files
- `get_object()` checks ownership and returns 403 (not 404) if it's someone else's file
- All protected routes require `IsAuthenticated`

**Appwrite:**
- The adapter queries documents where `ownerId` matches the logged-in user
- Also double-checks ownership when fetching a single file

### What Appwrite does vs what I did

Appwrite handles password hashing, session management, rate limiting, and CORS automatically. I didn't have to write any of that.

What I did: set up the collection schema, permissions, the ownerId index, and wrote the adapter that translates our API routes into Appwrite REST calls. The adapter also does its own ownership check as extra protection.

### What I'd improve with more time

- Actual file upload/download through Appwrite Storage (right now it's just metadata)
- Docker Compose so you can start everything with one command
- HTTPS in production
- IP-based rate limiting on Django (right now it only locks out after 5 failed logins)
- A refresh token button in the test client

---

## Running both at the same time

```bash
# terminal 1 — Django backend
cd custom-backend && python manage.py runserver 8001

# terminal 2 — web client
cd web && python -m http.server 8080
```

Open `http://localhost:8080/index.html` and use the radio buttons to switch between Mock / Custom / Appwrite modes.
