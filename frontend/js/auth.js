// ═══════════════════════════════════════════════════════
//  auth.js — Login & Signup form handlers
// ═══════════════════════════════════════════════════════

const API_BASE = (typeof window !== "undefined" && (window.location.protocol === "http:" || window.location.protocol === "https:") && window.location.port === "8000")
  ? window.location.origin
  : "http://127.0.0.1:8000";

// ── Helpers ─────────────────────────────────────────────

/**
 * Show or hide the error message banner on the page.
 * Targets the inner <span> to preserve the SVG icon.
 * @param {string|null} message — pass null to hide the banner
 */
function showError(message) {
  const el   = document.getElementById("auth-error");
  const span = el ? el.querySelector("span") : null;
  if (!el) return;
  if (message) {
    // Update only the text span — leave the SVG icon intact
    if (span) span.textContent = message;
    else el.textContent = message; // fallback
    el.classList.remove("hidden");
    el.classList.add("flex");
    // Scroll the error into view
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } else {
    el.classList.add("hidden");
    el.classList.remove("flex");
  }
}

/** Set button to loading state and disable it */
function setLoading(btn, loading) {
  if (!btn) return;
  if (loading) {
    btn.disabled = true;
    btn.dataset.originalText = btn.innerHTML;
    btn.innerHTML = `
      <span class="flex items-center justify-center gap-2">
        <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
        </svg>
        Processing…
      </span>`;
  } else {
    btn.disabled = false;
    btn.innerHTML = btn.dataset.originalText || "Submit";
  }
}

// ── Login Handler ────────────────────────────────────────

const loginForm = document.getElementById("login-form");
if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    showError(null);

    const email    = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const btn      = document.getElementById("login-btn");

    if (!email || !password) {
      showError("Please fill in all fields.");
      return;
    }

    setLoading(btn, true);

    let redirecting = false;

    try {
      // FastAPI OAuth2PasswordRequestForm expects form-urlencoded
      // and uses the "username" field as the identifier (we pass the email)
      const formData = new URLSearchParams();
      formData.append("username", email);
      formData.append("password", password);

      const resp = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData.toString(),
      });

      const data = await resp.json();

      if (!resp.ok) {
        // FastAPI raises 403 for wrong credentials → detail: "Invalid credentials"
        showError(data.detail || "Login failed. Please check your credentials.");
        return;
      }

      // ✅ Success — save token, role, and redirect
      redirecting = true;
      localStorage.setItem("token", data.access_token);
      if (data.role) {
        localStorage.setItem("role", data.role);
      }
      if (data.name) {
        localStorage.setItem("userName", data.name);
      }

      // If user is admin, redirect to admin.html, otherwise index.html
      if (data.role === "admin") {
        window.location.href = "admin.html";
      } else {
        window.location.href = "index.html";
      }

    } catch (err) {
      console.error("Login error:", err);
      showError(
        "Could not reach the server. " +
        "Make sure the backend is running: uvicorn backend.main:app --reload --port 8000"
      );
    } finally {
      // Don't undo the loading state if we're navigating away
      if (!redirecting) setLoading(btn, false);
    }
  });
}

// ── Signup Handler ───────────────────────────────────────

const signupForm = document.getElementById("signup-form");
if (signupForm) {
  signupForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    showError(null);

    const name     = document.getElementById("signup-name").value.trim();
    const email    = document.getElementById("signup-email").value.trim();
    const password = document.getElementById("signup-password").value;
    const mob_no   = document.getElementById("signup-mob")?.value.trim() || null;
    const btn      = document.getElementById("signup-btn");

    if (!name || !email || !password) {
      showError("Please fill in all required fields.");
      return;
    }

    if (password.length < 6) {
      showError("Password must be at least 6 characters.");
      return;
    }

    setLoading(btn, true);

    try {
      // POST /user expects a JSON body
      const payload = { name, email, password };
      if (mob_no) payload.mob_no = mob_no;

      const resp = await fetch(`${API_BASE}/user`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await resp.json();

      if (!resp.ok) {
        showError(data.detail || "Registration failed. Please try again.");
        return;
      }

      // Registration succeeded — now auto-login to get the JWT
      const formData = new URLSearchParams();
      formData.append("username", email);
      formData.append("password", password);

      const loginResp = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData.toString(),
      });

      const loginData = await loginResp.json();

      if (loginResp.ok && loginData.access_token) {
        localStorage.setItem("token", loginData.access_token);
        window.location.href = "index.html";
      } else {
        // Registration worked but auto-login failed — send them to login page
        window.location.href = "login.html?registered=1";
      }
    } catch (err) {
      console.error("Signup error:", err);
      showError("Could not reach the server. Make sure the backend is running on port 8000.");
    } finally {
      setLoading(btn, false);
    }
  });
}
