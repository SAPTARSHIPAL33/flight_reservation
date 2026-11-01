// ═══════════════════════════════════════════════════════
//  dashboard.js — My Bookings (Protected Page)
// ═══════════════════════════════════════════════════════

const API_BASE = (typeof window !== "undefined" && (window.location.protocol === "http:" || window.location.protocol === "https:") && window.location.port === "8000")
  ? window.location.origin
  : "http://127.0.0.1:8000";

// ── Auth Guard ───────────────────────────────────────────
// Redirect immediately if there's no token in localStorage
if (!localStorage.getItem("token")) {
  window.location.replace("login.html");
}

// Show Admin link if user is admin
const userRole = localStorage.getItem("role");
const adminLink = document.getElementById("link-admin");
if (adminLink && userRole === "admin") {
  adminLink.classList.remove("hidden");
  adminLink.classList.add("flex");
}

// ── DOM references ───────────────────────────────────────
const bookingsContainer = document.getElementById("bookings-container");
const bookingsSection   = document.getElementById("bookings-section");
const logoutBtn         = document.getElementById("btn-logout");
const toastEl           = document.getElementById("toast");

// ── Toast notification ───────────────────────────────────
let toastTimer;
function showToast(message, type = "success") {
  if (!toastEl) return;
  toastEl.textContent  = message;
  toastEl.className    = [
    "fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl text-sm font-medium shadow-xl transition-all duration-300",
    type === "success"
      ? "bg-emerald-500/90 text-white border border-emerald-400/30"
      : "bg-red-500/90 text-white border border-red-400/30",
  ].join(" ");
  toastEl.style.opacity = "1";
  toastEl.style.transform = "translateY(0)";

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastEl.style.opacity = "0";
    toastEl.style.transform = "translateY(12px)";
  }, 3500);
}

// ── Status badge helper ──────────────────────────────────
function statusBadge(status) {
  const map = {
    confirmed:    "bg-emerald-500/15 text-emerald-300 border-emerald-500/20",
    waiting_list: "bg-amber-500/15  text-amber-300  border-amber-500/20",
    cancelled:    "bg-red-500/15    text-red-300    border-red-500/20",
  };
  const label = {
    confirmed:    "✓ Confirmed",
    waiting_list: "⏳ Waitlist",
    cancelled:    "✕ Cancelled",
  };
  const cls = map[status] || "bg-slate-500/15 text-slate-300 border-slate-500/20";
  return `<span class="inline-block px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider border rounded-full ${cls}">${label[status] || status}</span>`;
}

// ── Build a single booking card ──────────────────────────
function buildBookingCard(booking, index) {
  const isCancelled = booking.status === "cancelled";

  return `
    <div id="card-${booking.booking_id}"
         class="booking-card glass rounded-2xl p-6 transition-all duration-300 hover:border-brand-500/25"
         style="animation: cardIn 0.45s cubic-bezier(0.16,1,0.3,1) ${index * 60}ms both">

      <!-- Header row -->
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
          <!-- Flight icon badge -->
          <div class="w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/15 flex items-center justify-center shrink-0">
            <svg class="w-5 h-5 text-brand-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.125A59.768 59.768 0 0121.485 12 59.768 59.768 0 013.27 20.875L5.999 12zm0 0h7.5"/>
            </svg>
          </div>
          <div>
            <p class="text-xs text-slate-400 uppercase tracking-wider">Booking ID</p>
            <p class="text-sm font-bold text-white">#${booking.booking_id}</p>
          </div>
        </div>
        ${statusBadge(booking.status)}
      </div>

      <!-- Flight details grid -->
      <div class="grid grid-cols-2 gap-3 mb-5">
        <div class="bg-white/5 rounded-xl p-3">
          <p class="text-[10px] text-slate-400 uppercase tracking-wider mb-1">Flight ID</p>
          <p class="text-sm font-semibold text-white">#${booking.flight_id}</p>
        </div>
        <div class="bg-white/5 rounded-xl p-3">
          <p class="text-[10px] text-slate-400 uppercase tracking-wider mb-1">Passenger ID</p>
          <p class="text-sm font-semibold text-white">#${booking.passenger_id}</p>
        </div>
      </div>

      <!-- Cancel button -->
      ${!isCancelled ? `
        <button
          id="cancel-btn-${booking.booking_id}"
          data-booking-id="${booking.booking_id}"
          onclick="cancelBooking(${booking.booking_id})"
          class="cancel-btn w-full py-2.5 text-sm font-semibold text-red-300 border border-red-500/20 bg-red-500/5 hover:bg-red-500/15 hover:border-red-500/40 rounded-xl transition-all duration-200 focus:outline-none">
          Cancel Ticket
        </button>
      ` : `
        <p class="text-center text-xs text-slate-500 py-2">This booking has been cancelled.</p>
      `}
    </div>`;
}

// ── Render all bookings ──────────────────────────────────
function renderBookings(bookings) {
  if (!bookingsContainer) return;

  if (!bookings || bookings.length === 0) {
    bookingsContainer.innerHTML = `
      <div class="flex flex-col items-center justify-center py-20 gap-4 text-center">
        <div class="w-16 h-16 rounded-full bg-slate-500/10 flex items-center justify-center">
          <svg class="w-8 h-8 text-slate-500" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.125A59.768 59.768 0 0121.485 12 59.768 59.768 0 013.27 20.875L5.999 12zm0 0h7.5"/>
          </svg>
        </div>
        <p class="text-slate-400 text-sm">You have no bookings yet.</p>
        <a href="index.html"
           class="mt-2 px-5 py-2 text-sm font-semibold text-white bg-gradient-to-r from-brand-600 to-brand-500 rounded-xl hover:from-brand-500 hover:to-brand-400 transition-all shadow-lg shadow-brand-600/25">
          Search Flights
        </a>
      </div>`;
    return;
  }

  const activeCount    = bookings.filter(b => b.status !== "cancelled").length;
  const cancelledCount = bookings.filter(b => b.status === "cancelled").length;

  // Summary row
  const summaryHTML = `
    <div class="flex flex-wrap gap-4 mb-8">
      <div class="glass rounded-xl px-5 py-3 flex items-center gap-3">
        <div class="w-2 h-2 rounded-full bg-emerald-400"></div>
        <span class="text-sm text-slate-300"><span class="font-bold text-white">${activeCount}</span> Active</span>
      </div>
      <div class="glass rounded-xl px-5 py-3 flex items-center gap-3">
        <div class="w-2 h-2 rounded-full bg-red-400"></div>
        <span class="text-sm text-slate-300"><span class="font-bold text-white">${cancelledCount}</span> Cancelled</span>
      </div>
    </div>`;

  const cardsHTML = bookings.map((b, i) => buildBookingCard(b, i)).join("");
  bookingsContainer.innerHTML = summaryHTML + `<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">${cardsHTML}</div>`;
}

// ── Cancel a booking ─────────────────────────────────────
async function cancelBooking(bookingId) {
  const btn = document.getElementById(`cancel-btn-${bookingId}`);
  if (!btn) return;

  // Confirm before acting
  if (!confirm("Are you sure you want to cancel this booking?")) return;

  // Disable button while in flight
  btn.disabled  = true;
  btn.textContent = "Cancelling…";

  try {
    const resp = await fetchWithAuth(`/cancel/${bookingId}`, { method: "PUT" });

    if (resp.status === 401) return; // fetchWithAuth already redirected

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || "Could not cancel booking. Please try again.", "error");
      btn.disabled    = false;
      btn.textContent = "Cancel Ticket";
      return;
    }

    // Update the card UI in-place without a full reload
    const card = document.getElementById(`card-${bookingId}`);
    if (card) {
      // Fade out, then replace button with cancelled state
      card.style.opacity = "0.6";
      btn.outerHTML = `<p class="text-center text-xs text-slate-500 py-2">This booking has been cancelled.</p>`;

      // Update status badge
      const badgeEl = card.querySelector("span[class*='border rounded-full']");
      if (badgeEl) badgeEl.outerHTML = statusBadge("cancelled");
    }

    showToast("Booking cancelled successfully.", "success");
  } catch (err) {
    console.error("Cancel error:", err);
    showToast("Could not reach the server.", "error");
    btn.disabled    = false;
    btn.textContent = "Cancel Ticket";
  }
}

// ── Load bookings on page startup ────────────────────────
async function loadBookings() {
  bookingsContainer.innerHTML = `
    <div class="flex flex-col items-center justify-center py-20 gap-4">
      <div class="spinner"></div>
      <p class="text-sm text-slate-400 animate-pulse">Loading your bookings…</p>
    </div>`;

  try {
    const resp = await fetchWithAuth("/my-bookings");
    if (resp.status === 401) return; // already redirected by fetchWithAuth

    if (!resp.ok) {
      throw new Error(`Server error ${resp.status}`);
    }

    const bookings = await resp.json();
    renderBookings(bookings);
  } catch (err) {
    console.error("Load bookings error:", err);
    bookingsContainer.innerHTML = `
      <div class="flex flex-col items-center justify-center py-20 gap-3 text-center">
        <svg class="w-8 h-8 text-red-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <p class="text-sm text-red-300">Failed to load bookings. Please refresh.</p>
      </div>`;
  }
}

// ── Logout ────────────────────────────────────────────────
if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("token");
    window.location.href = "index.html";
  });
}

// ── Kick off ─────────────────────────────────────────────
loadBookings();
