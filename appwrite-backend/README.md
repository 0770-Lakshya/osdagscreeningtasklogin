# Appwrite Backend



- `appwrite-adapter.js` — The adapter that intercepts `window.fetch` calls and routes them to Appwrite's REST API



The adapter patches `window.fetch` when Appwrite mode is selected in `index.html`. It maps our API routes to Appwrite endpoints:

| Our Route | Appwrite API |
| POST /register | POST /v1/account |
| POST /login | POST /v1/account/sessions |
| POST /logout | DELETE /v1/account/sessions/current |
| GET /me | GET /v1/account |
| GET /files | GET /v1/databases/.../documents (with ownerId filter) |
| GET /files/:id | GET /v1/databases/.../documents/:id |

## For setup

See the main [README.md] for Appwrite setup instructions.

## Key features

- Auto-seeds 2 sample files per user after login
- Uses simple numeric file IDs (1, 2, 3...)
- Data isolation: only returns files where ownerId matches logged-in user
- Uses `nativeFetch` (original browser fetch) to avoid conflicts with mock-api.js
