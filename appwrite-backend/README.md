# Appwrite Backend

This folder has one file: `appwrite-adapter.js`. It makes the shared test client talk to Appwrite Cloud instead of a custom server.

## How it works

The adapter patches `window.fetch` when Appwrite mode is selected. It maps our API routes to Appwrite REST API endpoints:

| Our Route | Appwrite API |
|---|---|
| POST /register | POST /v1/account |
| POST /login | POST /v1/account/sessions |
| POST /logout | DELETE /v1/account/sessions/current |
| GET /me | GET /v1/account |
| GET /files | GET /v1/databases/.../documents (with ownerId filter) |
| GET /files/:id | GET /v1/databases/.../documents/:id (with ownership check) |

## How it gets loaded

`web/index.html` loads this file with:
```html
<script src="../appwrite-backend/appwrite-adapter.js"></script>
```

This keeps the two backends in separate folders while sharing the same frontend.

## How authentication works

Appwrite uses cookie-based sessions. When you login, Appwrite sets an httpOnly cookie in the browser. Every subsequent request sends this cookie automatically via `credentials: "include"`. The adapter doesn't need to store or pass any session token — the browser handles it.

When you logout, the adapter sends `DELETE /v1/account/sessions/current`. The cookie is included automatically, so Appwrite knows which session to destroy.

## Key features

- Auto-seeds 2 sample files per user after login
- Uses simple file IDs (1, 2, 3...)
- Data isolation: only returns files where ownerId matches the logged-in user
- Uses `nativeFetch` (the original browser fetch) to avoid conflicts with mock-api.js
- Stores session in `sessionStorage` so it persists across page reloads but clears when the tab closes

## Setup

See the main [README.md](../README.md) for full Appwrite setup instructions.
