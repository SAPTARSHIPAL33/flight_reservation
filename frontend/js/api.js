// ═══════════════════════════════════════════════════════
//  api.js — Centralized fetch utility with JWT auth
// ═══════════════════════════════════════════════════════

// Safely declare global API_BASE without collision across multiple scripts
if (typeof window !== "undefined" && !window.API_BASE) {
  window.API_BASE = ((window.location.protocol === "http:" || window.location.protocol === "https:") && window.location.port === "8000")
    ? window.location.origin
    : "http://127.0.0.1:8000";
}
var API_BASE = (typeof window !== "undefined" && window.API_BASE) ? window.API_BASE : "http://127.0.0.1:8000";

/**
 * A wrapper around fetch() that automatically:
 *   1. Retrieves the JWT token from localStorage
 *   2. Attaches it as an Authorization: Bearer header on every request
 *   3. On a 401 response, clears the token and redirects to login.html
 *
 * @param {string} endpoint — Path relative to API_BASE (e.g. "/user/me")
 * @param {RequestInit} options — Standard fetch options (method, body, headers, etc.)
 * @returns {Promise<Response>} — The raw fetch Response (caller handles .json())
 */
async function fetchWithAuth(endpoint, options = {}) {
  const token = localStorage.getItem("token");

  // Merge caller-supplied headers with the Authorization header
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  // Auto-logout on any 401 Unauthorized response
  if (response.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "login.html";
    return response; // return so callers don't throw on the redirect path
  }

  return response;
}
