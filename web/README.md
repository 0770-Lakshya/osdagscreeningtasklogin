# Web 

## Files

- `index.html` — The required GUI. Has 3 modes: Mock, Custom backend, Appwrite
- `mock-api.js` — In-browser mock backend (for quick demo without a real backend)
- `seed-data.json` — Sample data for mock mode (3 users, 6 files)

## Use
1. Start a web server in this folder:
   ```bash
   python -m http.server 8080
   ```

2. Open `http://localhost:8080/index.html`

3. Select your backend mode:
   - **Mock** — works immediately, no backend needed
   - **Custom REST backend** — requires Django running on port 8001
   - **Appwrite** — requires Appwrite Cloud project

## Backend modes

### Mock mode
- Uses `mock-api.js` and `seed-data.json`
- Everything runs in the browser
- Good for quick demos

### Custom REST backend mode
- Hits `http://localhost:8001` by default
- Requires Django backend to be running
- Uses JWT tokens in Authorization header

### Appwrite mode
- Hits Appwrite Cloud REST API
- Requires Appwrite project setup (see main README)
- Uses session tokens via X-Appwrite-Session header
