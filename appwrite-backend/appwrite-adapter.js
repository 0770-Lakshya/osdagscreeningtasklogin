/**
 * appwrite-adapter.js
 * intercepts fetch calls when Appwrite radio is selected,
 * routes them to Appwrite REST API
 *
 * NOTE: this works by overriding window.fetch so index.html
 * doesn't need to change — the same fetch("/login", ...) call
 * just goes to Appwrite instead of a real server
 */

(function () {
  // grab the real browser fetch before mock-api.js patches it
  var nativeFetch = window.__nativeFetch || window.fetch.bind(window);

  function json(status, body) {
    return new Response(JSON.stringify(body), {
      status: status,
      headers: { "Content-Type": "application/json" },
    });
  }

  function getConfig() {
    return {
      endpoint: document.getElementById("awEndpoint").value.replace(/\/$/, ""),
      projectId: document.getElementById("awProjectId").value,
      databaseId: document.getElementById("awDatabaseId").value,
      collectionId: document.getElementById("awFilesCollectionId").value,
      bucketId: document.getElementById("awBucketId").value,
    };
  }

  function isAppwriteMode() {
    var radio = document.querySelector('input[name="backendMode"]:checked');
    return radio && radio.value === "appwrite";
  }

  // session is stored in sessionStorage so it persists across page reloads
  // but clears when the browser tab is closed
  var SESSION_KEY = "appwrite_session";

  function saveSession(data) {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
  }

  function getSession() {
    try {
      return JSON.parse(sessionStorage.getItem(SESSION_KEY));
    } catch (e) {
      return null;
    }
  }

  function clearSession() {
    sessionStorage.removeItem(SESSION_KEY);
  }

  function generateId() {
    // not using crypto.randomUUID because we need something that
    // works in older browsers too
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }

  // keeps track of the next file ID to assign (1, 2, 3, ...)
  var nextFileId = 1;

  // ---- Appwrite REST API helper ----
  // this uses nativeFetch directly (the real browser fetch) so it
  // doesn't get intercepted by our own fetch override below
  async function awRequest(method, path, body, sessionToken) {
    var cfg = getConfig();
    var fullUrl = cfg.endpoint + path;

    var headers = {
      "X-Appwrite-Project": cfg.projectId,
      "Content-Type": "application/json",
    };

    if (sessionToken) {
      headers["X-Appwrite-Session"] = sessionToken;
    }

    var opts = { method: method, headers: headers };
    if (body) opts.body = JSON.stringify(body);

    var res = await nativeFetch(fullUrl, opts);
    var data = await res.json().catch(function () { return {}; });
    return { status: res.status, data: data };
  }

  // ---- Seed files for a user after login ----
  // each user gets 2 sample files with simple numeric IDs (1, 2, 3, etc)
  async function seedFilesForUser(userId, sessionToken) {
    var cfg = getConfig();

    // check if user already has files (don't re-seed)
    var queryObj = JSON.stringify({ method: "equal", attribute: "ownerId", values: [userId] });
    var checkPath = "/databases/" + cfg.databaseId + "/collections/" + cfg.collectionId + "/documents?queries[]=" + encodeURIComponent(queryObj);
    var checkRes = await awRequest("GET", checkPath, null, sessionToken);
    if (checkRes.status === 200 && checkRes.data.documents && checkRes.data.documents.length > 0) {
      return; // already has files, skip
    }

    console.log("[appwrite-adapter] seeding files for user:", userId);

    // figure out what the next ID should be so we don't collide
    var allQuery = JSON.stringify({ method: "orderDesc", attribute: "$id" });
    var allPath = "/databases/" + cfg.databaseId + "/collections/" + cfg.collectionId + "/documents?queries[]=" + encodeURIComponent(allQuery) + "&queries[]=" + encodeURIComponent(JSON.stringify({ method: "limit", values: [1] }));
    var allRes = await awRequest("GET", allPath, null, sessionToken);
    if (allRes.status === 200 && allRes.data.documents && allRes.data.documents.length > 0) {
      var maxId = parseInt(allRes.data.documents[0].$id, 10);
      if (!isNaN(maxId) && maxId >= nextFileId) {
        nextFileId = maxId + 1;
      }
    }

    // create 2 sample files
    var sampleFiles = [
      { name: "resume_" + userId.slice(0, 6) + ".pdf", des: "Resume document", size: 84213 },
      { name: "profile_photo.jpg", des: "Profile photo", size: 231044 },
    ];

    for (var i = 0; i < sampleFiles.length; i++) {
      var f = sampleFiles[i];
      var fileId = String(nextFileId++);
      var docPath = "/databases/" + cfg.databaseId + "/collections/" + cfg.collectionId + "/documents";
      await awRequest("POST", docPath, {
        documentId: fileId,
        data: {
          ownerId: userId,
          name: f.name,
          des: f.des,
          size: f.size,
        },
      }, sessionToken);
    }
  }

  // ---- route handlers ----

  async function handleRegister(body) {
    var email = body && body.email;
    var password = body && body.password;
    if (!email || !password) return json(400, { error: "email and password are required" });

    try {
      var userId = generateId();
      var createRes = await awRequest("POST", "/account", {
        userId: userId,
        email: email,
        password: password,
        name: email.split("@")[0],
      });

      if (createRes.status !== 201) {
        if (createRes.status === 409) {
          return json(409, { error: "An account with that email already exists" });
        }
        return json(createRes.status, { error: createRes.data.message || "Registration failed" });
      }

      // auto-login after registration
      var sessionRes = await awRequest("POST", "/account/sessions", {
        email: email,
        password: password,
        provider: "email",
      });

      if (sessionRes.status !== 201) {
        return json(201, {
          user: { id: createRes.data.$id, email: createRes.data.email },
          note: "Account created but auto-login failed. Please login manually.",
        });
      }

      clearSession();
      saveSession({ sessionId: sessionRes.data.$id, userId: createRes.data.$id });

      // seed some files for the new user
      await seedFilesForUser(createRes.data.$id, sessionRes.data.$id);

      return json(201, {
        user: { id: createRes.data.$id, email: createRes.data.email },
        token: sessionRes.data.$id,
      });
    } catch (e) {
      console.error("[appwrite-adapter] register error:", e);
      return json(500, { error: e.message || "Registration failed" });
    }
  }

  async function handleLogin(body) {
    var email = body && body.email;
    var password = body && body.password;
    if (!email || !password) return json(400, { error: "email and password are required" });

    try {
      // clear old session first — Appwrite has a limit on active sessions
      var oldSession = getSession();
      if (oldSession && oldSession.sessionId) {
        try {
          await awRequest("DELETE", "/account/sessions/" + oldSession.sessionId, null, oldSession.sessionId);
        } catch (e) { /* whatever, it'll get cleaned up */ }
      }
      clearSession();

      var sessionRes = await awRequest("POST", "/account/sessions", {
        email: email,
        password: password,
        provider: "email",
      });

      if (sessionRes.status !== 201) {
        // generic error — don't reveal if email exists or not
        return json(401, { error: "Invalid email or password." });
      }

      // grab the user profile
      var userRes = await awRequest("GET", "/account", null, sessionRes.data.$id);
      var user = userRes.data;

      saveSession({ sessionId: sessionRes.data.$id, userId: user.$id });

      // make sure they have some files
      await seedFilesForUser(user.$id, sessionRes.data.$id);

      return json(200, {
        user: { id: user.$id, email: user.email },
        token: sessionRes.data.$id,
      });
    } catch (e) {
      console.error("[appwrite-adapter] login error:", e);
      return json(401, { error: "Invalid email or password." });
    }
  }

  async function handleLogout() {
    var session = getSession();
    if (session) {
      try {
        await awRequest("DELETE", "/account/sessions/" + session.sessionId, null, session.sessionId);
      } catch (e) { /* ok */ }
    }
    clearSession();
    return json(200, { detail: "Logged out." });
  }

  async function handleMe() {
    var session = getSession();
    if (!session) return json(401, { detail: "Not authenticated." });

    try {
      var res = await awRequest("GET", "/account", null, session.sessionId);
      if (res.status !== 200) {
        clearSession(); // session expired probably
        return json(401, { detail: "Not authenticated." });
      }

      return json(200, {
        id: res.data.$id,
        email: res.data.email,
        full_name: res.data.name || "",
        date_joined: res.data.$createdAt,
      });
    } catch (e) {
      return json(401, { detail: "Not authenticated." });
    }
  }

  async function handleFiles() {
    var session = getSession();
    if (!session) return json(401, { detail: "Not authenticated." });

    try {
      var cfg = getConfig();
      // Appwrite queries use JSON format (not the old equal("attr","val") syntax)
      var queryObj = JSON.stringify({ method: "equal", attribute: "ownerId", values: [session.userId] });
      var docPath = "/databases/" + cfg.databaseId + "/collections/" + cfg.collectionId + "/documents?queries[]=" + encodeURIComponent(queryObj);

      var res = await awRequest("GET", docPath, null, session.sessionId);

      if (res.status !== 200) {
        console.error("[appwrite-adapter] files failed:", res.status, res.data);
        return json(res.status, { error: res.data.message || "Failed to list files" });
      }

      var files = (res.data.documents || []).map(function (doc) {
        return {
          id: doc.$id,
          ownerId: doc.ownerId,
          fileName: doc.name || "unknown",
          mimeType: doc.mimeType || "application/octet-stream",
          sizeBytes: doc.size || 0,
          uploadedAt: doc.uploadedAt || doc.$createdAt,
        };
      });

      return json(200, { files: files });
    } catch (e) {
      console.error("[appwrite-adapter] files error:", e);
      return json(401, { detail: "Not authenticated." });
    }
  }

  async function handleFileById(fileId) {
    var session = getSession();
    if (!session) return json(401, { detail: "Not authenticated." });

    try {
      var cfg = getConfig();
      var res = await awRequest(
        "GET",
        "/databases/" + cfg.databaseId + "/collections/" + cfg.collectionId + "/documents/" + fileId,
        null,
        session.sessionId
      );

      if (res.status === 404) return json(404, { error: "File not found" });
      if (res.status === 401 || res.status === 403) {
        return json(403, { error: "You do not have access to this file" });
      }

      var doc = res.data;

      // double-check ownership — Appwrite permissions should handle this
      // but better to be safe
      if (doc.ownerId !== session.userId) {
        return json(403, { error: "You do not have access to this file" });
      }

      return json(200, {
        file: {
          id: doc.$id,
          ownerId: doc.ownerId,
          fileName: doc.name || "unknown",
          mimeType: doc.mimeType || "application/octet-stream",
          sizeBytes: doc.size || 0,
          uploadedAt: doc.uploadedAt || doc.$createdAt,
        },
      });
    } catch (e) {
      return json(500, { error: "Server error" });
    }
  }

  async function handleFileDownload(fileId) {
    var session = getSession();
    if (!session) return new Response("Not authenticated", { status: 401 });

    try {
      var cfg = getConfig();

      var docRes = await awRequest(
        "GET",
        "/databases/" + cfg.databaseId + "/collections/" + cfg.collectionId + "/documents/" + fileId,
        null,
        session.sessionId
      );

      if (docRes.status === 404) return new Response("File not found", { status: 404 });
      if (docRes.status === 403) return new Response("Forbidden", { status: 403 });

      var doc = docRes.data;

      if (doc.ownerId !== session.userId) {
        return new Response("Forbidden", { status: 403 });
      }

      var storageFileId = doc.storageFileId;

      if (!storageFileId) {
        // no actual file in storage, just return a placeholder
        var placeholder = "File \"" + (doc.name || "unknown") + "\" — no file content uploaded to storage.";
        return new Response(placeholder, {
          status: 200,
          headers: { "Content-Type": "text/plain", "Content-Disposition": 'attachment; filename="' + (doc.name || "file") + '"' },
        });
      }

      var fileRes = await nativeFetch(
        cfg.endpoint + "/storage/buckets/" + cfg.bucketId + "/files/" + storageFileId + "/download",
        { headers: { "X-Appwrite-Project": cfg.projectId, "X-Appwrite-Session": session.sessionId } }
      );

      if (!fileRes.ok) return new Response("File not found", { status: 404 });

      return new Response(fileRes.body, {
        status: 200,
        headers: {
          "Content-Type": doc.mimeType || "application/octet-stream",
          "Content-Disposition": 'attachment; filename="' + (doc.name || "file") + '"',
        },
      });
    } catch (e) {
      return new Response("Server error", { status: 500 });
    }
  }

  // ---- hook into window.fetch ----
  window.fetch = async function (input, init) {
    if (!isAppwriteMode()) return nativeFetch(input, init);

    var url = typeof input === "string" ? input : input.url;
    var pathname;
    try {
      pathname = new URL(url, window.location.href).pathname;
    } catch (e) {
      pathname = url;
    }

    var method = (init && init.method) || "GET";

    // small delay to make it feel like a real network request
    await new Promise(function (r) { setTimeout(r, 100); });

    var postBody = null;
    if (init && init.body) {
      try { postBody = JSON.parse(init.body); } catch (e) { postBody = {}; }
    }

    if (pathname === "/register" && method === "POST") return handleRegister(postBody);
    if (pathname === "/login" && method === "POST") return handleLogin(postBody);
    if (pathname === "/logout" && method === "POST") return handleLogout();
    if (pathname === "/me" && method === "GET") return handleMe();
    if (pathname === "/files" || pathname === "/files/") return handleFiles();

    var m = pathname.match(/^\/files\/([^/]+)\/download$/);
    if (m && method === "GET") return handleFileDownload(m[1]);

    m = pathname.match(/^\/files\/([^/]+)$/);
    if (m && method === "GET") return handleFileById(m[1]);

    return json(404, { error: "No route for " + method + " " + pathname });
  };

  console.info("[appwrite-adapter] ready");
})();
