# Web Client

This folder has the shared test client that works with all three backend modes.

## Files

- `index.html` — The required GUI. Has 3 modes: Mock, Custom backend, Appwrite
- `mock-api.js` — In-browser mock backend (for quick demo without a real backend)
- `seed-data.json` — Sample data for mock mode (3 users, 6 files)

The Appwrite adapter (`appwrite-adapter.js`) lives in `../appwrite-backend/` and is loaded from `index.html` using a relative path.

## How to run

1. Start a web server in this folder:
   ```bash
   python -m http.server 8080
   ```

2. Open `http://localhost:8080/index.html`

3. Pick your backend mode:
   - **Mock** — works right away, no backend needed
   - **Custom REST backend** — needs Django running on port 8001
   - **Appwrite** — needs Appwrite Cloud project

## Backend modes

### Mock mode
- Uses `mock-api.js` and `seed-data.json`
- Everything runs in the browser
- Good for quick demos without any setup

### Custom REST backend mode
- Hits `http://localhost:8001` by default
- Needs Django backend running
- Uses JWT tokens in the Authorization header

### Appwrite mode
- Hits Appwrite Cloud REST API directly from the browser
- Needs Appwrite project setup (see main README)
- Uses cookie-based sessions via `credentials: "include"`
- The adapter file is loaded from `../appwrite-backend/appwrite-adapter.js`
