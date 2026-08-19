# Secure Login System

This is my submission for the OSDAG IIT Bombay task.

- **Custom backend**: Django + DRF + JWT (SQLite for now, can swap to Postgres)
- **Appwrite backend**: Appwrite Cloud, with a JS adapter in the browser

---

## Project structure

```
├── custom-backend/               # Django backend 1
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── config/                   # settings, urls, wsgi
│   ├── users/                    # register, login, logout, me
│   │   └── management/commands/seed_demo.py
│   └── files/                    # file list, detail, download
│
├── appwrite-backend/             # Appwrite backend 2
│   └── appwrite-adapter.js       # the adapter that talks to Appwrite REST API
│
├── web/                          
│   ├── index.html                
│   ├── mock-api.js               # in-browser mock for quick demo
│   ├── seed-data.json            # mock seed data
│   
├── README.md
```

---

## Running the Django backend

```bash
cd custom-backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # optional, sqlite works fine without it
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

## API endpoints

Both backends expose these routes:

| Method | Route | Auth | What it does |
| POST | `/register` | no | create account |
| POST | `/login` | no | login, returns tokens |
| POST | `/logout` | yes | invalidate session |
| POST | `/refresh` | no | get new token pair |
| GET | `/me` | yes | current user profile |
| GET | `/files` | yes | list user's files |
| GET | `/files/:id` | yes | get single file (403 if not his/her) |
| GET | `/files/:id/download` | yes | download file |

---

## Why I made these choices
### JWT vs sessions
I went with JWT for Django because it's stateless — the server doesn't need to hit the database on every request to verify who you are. That said, I do store refresh tokens server-side (hashed with SHA-256) so they can be revoked when you log out. Best of both worlds, I guess.

Appwrite handles sessions on its own, so the adapter just passes the session secret around.

### How logout works
When you logout from Django, the server does two things:
1. Deletes the refresh token row from the database
2. Adds the access token's `jti` (unique ID inside the JWT) to a blacklist table

So even if someone still has a valid-looking access token, it gets rejected because of the blacklist check. The token "looks" valid but the server knows it's been logged out.

For Appwrite it's simpler — `account.deleteSession("current")` and Appwrite takes care of it.

### Data isolation (the main security thing)
This is what the task cares about most, so as i was.

**Django:**
- `get_queryset()` filters by `owner=request.user` — you literally can't list someone else's files
- `get_object()` checks the owner and returns 403 (not 404) if it's someone else's file — this distinction matters for the task
- All protected routes have `IsAuthenticated`

**Appwrite:**
- The adapter queries docs where `ownerId` matches the logged-in user
- Also double-checks ownership when fetching a single file

### What Appwrite does vs what I did

Appwrite handles the hard stuff automatically: password hashing (argon2), session management, rate limiting, CORS. I didn't have to write any of that.

What I configured: the collection schema, permissions, the ownerId index, and the adapter that translates our API routes into Appwrite REST calls. The adapter also does its own ownership check as an extra safety net.

### What I'd improve

- Actual file upload/download through Appwrite Storage (right now it's metadata only)
- E2E tests for the data isolation stuff
- Docker Compose so you can start everything with one command and i can also  add redis for caching and faster reloding.
- HTTPS in production
- Maybe IP-based rate limiting on Django too (right now it only locks out after 5 failed logins)

---

## Running both at the same time

```bash
# terminal 1 — Django backend
cd custom-backend && python manage.py runserver 8001

# terminal 2 — web client
cd web && python -m http.server 8080
```

Open `http://localhost:8080/index.html` and use the radio buttons to switch between Mock / Custom / Appwrite modes.
