// ═══════════════════════════════════════════════════════
//  dashboard.js — Passenger Dashboard (Multi-Leg & Waitlist)
// ═══════════════════════════════════════════════════════

// API_BASE is initialized by api.js
var API_BASE = (typeof window !== "undefined" && window.API_BASE)
  ? window.API_BASE
  : "http://127.0.0.1:8000";

// ── Auth Guard ───────────────────────────────────────────
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

// ── DOM References ───────────────────────────────────────
const upcomingContainer = document.getElementById("upcoming-container");
const waitlistContainer = document.getElementById("waitlist-container");
const historyContainer  = document.getElementById("history-container");

const countActiveEl   = document.getElementById("count-active");
const countWaitlistEl = document.getElementById("count-waitlist");
const countHistoryEl  = document.getElementById("count-history");

const badgeActiveEl   = document.getElementById("badge-active");
const badgeWaitlistEl = document.getElementById("badge-waitlist");
const badgeHistoryEl  = document.getElementById("badge-history");

const logoutBtn = document.getElementById("btn-logout");
const toastEl   = document.getElementById("toast");

// ── Toast Notification ───────────────────────────────────
let toastTimer;
function showToast(message, type = "success") {
  if (!toastEl) return;
  toastEl.textContent = message;
  toastEl.className = [
    "fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl text-sm font-semibold shadow-2xl transition-all duration-300",
    type === "success"
      ? "bg-emerald-600/95 text-white border border-emerald-400/40 shadow-emerald-500/20"
      : "bg-red-600/95 text-white border border-red-400/40 shadow-red-500/20",
  ].join(" ");
  toastEl.style.opacity = "1";
  toastEl.style.transform = "translateY(0)";

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastEl.style.opacity = "0";
    toastEl.style.transform = "translateY(12px)";
  }, 4000);
}

// ── Date & Time Formatters ───────────────────────────────
function formatDate(dtStr) {
  if (!dtStr) return "";
  try {
    const d = new Date(dtStr);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString("en-US", {
      weekday: "short",
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch (e) {
    return "";
  }
}

function formatTime(dtStr) {
  if (!dtStr) return "";
  try {
    const d = new Date(dtStr);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return "";
  }
}

function formatDuration(startStr, endStr) {
  if (!startStr || !endStr) return "";
  try {
    const diffMs = new Date(endStr).getTime() - new Date(startStr).getTime();
    if (isNaN(diffMs) || diffMs <= 0) return "";
    const totalMinutes = Math.floor(diffMs / 60000);
    const hours = Math.floor(totalMinutes / 60);
    const mins = totalMinutes % 60;
    return `${hours}h ${mins}m`;
  } catch (e) {
    return "";
  }
}

// ── Status Badge Helper ──────────────────────────────────
function statusBadge(status, sectionType, currentPosition) {
  const norm = (status || "").toLowerCase();
  if (sectionType === "history") {
    if (norm === "cancelled") {
      return `<span class="px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-rose-300 bg-rose-500/15 border border-rose-500/25 rounded-full">✕ Cancelled</span>`;
    }
    return `<span class="px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-slate-300 bg-slate-500/15 border border-slate-500/25 rounded-full">✓ Completed</span>`;
  }

  if (norm === "waiting_list" || norm === "pending" || sectionType === "waitlist") {
    const posText = currentPosition ? `Status: WL-${currentPosition}` : "Status: WL-Pending";
    return `<span class="inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-extrabold uppercase tracking-wider text-amber-950 bg-gradient-to-r from-amber-300 via-amber-400 to-yellow-400 border border-amber-400/60 rounded-full shadow-md shadow-amber-500/25">
      <span class="w-1.5 h-1.5 rounded-full bg-amber-950 animate-ping"></span>
      ${posText}
    </span>`;
  }

  if (norm === "confirmed") {
    return `<span class="px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-emerald-300 bg-emerald-500/15 border border-emerald-500/25 rounded-full">✓ Confirmed</span>`;
  }

  return `<span class="px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-slate-300 bg-slate-500/15 border border-slate-500/25 rounded-full">${status}</span>`;
}

// ── Route Connector Visualizer ───────────────────────────
function renderConnector(journey) {
  const layovers = Array.isArray(journey.layovers) ? journey.layovers : [];
  const isDirect = journey.total_stops === 0 || layovers.length === 0;

  if (isDirect) {
    return `
      <div class="flex-1 flex items-center px-2">
        <div class="flex-1 h-0.5 bg-gradient-to-r from-emerald-500/30 via-emerald-400 to-emerald-500/30"></div>
        <div class="w-7 h-7 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shrink-0 mx-1 shadow-sm" title="Direct Flight">
          <svg class="w-3.5 h-3.5 text-emerald-400" fill="currentColor" viewBox="0 0 24 24">
            <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/>
          </svg>
        </div>
        <div class="flex-1 h-0.5 bg-gradient-to-r from-emerald-500/30 via-emerald-400 to-emerald-500/30"></div>
      </div>
    `;
  }

  const segmentsHtml = layovers.map((code) => `
    <div class="flex-1 h-0.5 bg-amber-500/30 border-t border-dashed border-amber-400/50"></div>
    <div class="px-2 py-0.5 rounded-full bg-amber-500/20 border border-amber-400/50 flex items-center justify-center shrink-0 text-[10px] font-bold text-amber-200 shadow-sm" title="Layover at ${code}">
      ${code}
    </div>
  `).join("");

  return `
    <div class="flex-1 flex items-center px-2">
      ${segmentsHtml}
      <div class="flex-1 h-0.5 bg-amber-500/30 border-t border-dashed border-amber-400/50"></div>
    </div>
  `;
}

// ── Build a Single Journey Card ──────────────────────────
function buildJourneyCard(journey, sectionType, index) {
  const pnr = journey.pnr;
  const isHistory = sectionType === "history";
  const isWaitlist = sectionType === "waitlist";
  const legs = Array.isArray(journey.legs) ? journey.legs : [];
  const layovers = Array.isArray(journey.layovers) ? journey.layovers : [];
  const stopsLabel = journey.total_stops === 0 ? "Direct" : `${journey.total_stops} Layover${journey.total_stops > 1 ? "s" : ""}`;

  const depDateFormatted = formatDate(journey.departure_time);
  const depTimeFormatted = formatTime(journey.departure_time);
  const arrTimeFormatted = formatTime(journey.arrival_time);
  const durationFormatted = formatDuration(journey.departure_time, journey.arrival_time);

  // Muted styling for Travel History section
  const cardClasses = isHistory
    ? "glass rounded-2xl p-6 transition-all duration-300 opacity-65 grayscale-[30%] hover:opacity-90 hover:grayscale-0 hover:border-slate-500/40 bg-white/[0.02]"
    : isWaitlist
      ? "glass rounded-2xl p-6 transition-all duration-300 hover:border-amber-400/40 border-amber-500/20 shadow-lg shadow-amber-500/5 ring-1 ring-amber-400/20"
      : "glass rounded-2xl p-6 transition-all duration-300 hover:border-brand-500/40 border-white/10 shadow-lg shadow-brand-500/5";

  return `
    <div id="journey-card-${pnr}"
         class="journey-card animate-card-in relative flex flex-col justify-between ${cardClasses}"
         style="animation-delay: ${index * 60}ms">

      <div>
        <!-- Top row: PNR Badge & Status -->
        <div class="flex items-center justify-between mb-4 pb-3 border-b border-white/5">
          <div class="flex items-center gap-2">
            <span class="text-[10px] uppercase font-bold tracking-widest text-brand-300/80">PNR:</span>
            <span class="px-2.5 py-1 rounded-md bg-brand-500/20 border border-brand-400/30 text-white font-mono font-bold text-xs tracking-wider shadow-sm">
              ${pnr}
            </span>
          </div>
          ${statusBadge(journey.status, sectionType, journey.current_position)}
        </div>

        ${isWaitlist ? `
          <!-- Prominent Dynamic IRCTC Waitlist Status Banner -->
          <div class="mb-4 p-3.5 rounded-xl bg-gradient-to-r from-amber-500/15 via-amber-500/10 to-transparent border border-amber-500/30 flex items-center justify-between shadow-inner">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl bg-amber-400/20 border border-amber-400/50 text-amber-300 flex items-center justify-center font-black text-sm shadow-md">
                ${journey.current_position ? `WL` : `#`}
              </div>
              <div>
                <p class="text-[10px] uppercase font-extrabold text-amber-400 tracking-wider">Live Waitlist Queue</p>
                <p class="text-base font-black text-white tracking-tight">
                  Status: WL-${journey.current_position || "1"}
                </p>
              </div>
            </div>
            <span class="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-amber-200 bg-amber-500/25 rounded-lg border border-amber-400/40 shadow-sm">
              Priority Rank #${journey.current_position || "1"}
            </span>
          </div>
        ` : ""}

        <!-- Route Visualization (Origin, connector line with layovers, Destination) -->
        <div class="flex items-center gap-2 mb-4">
          <div class="text-left">
            <p class="text-2xl font-black text-white tracking-tight">${journey.source}</p>
            <p class="text-[10px] uppercase tracking-wider text-slate-400">Origin</p>
          </div>

          ${renderConnector(journey)}

          <div class="text-right">
            <p class="text-2xl font-black text-white tracking-tight">${journey.destination}</p>
            <p class="text-[10px] uppercase tracking-wider text-slate-400">Destination</p>
          </div>
        </div>

        <!-- Schedule details: Date & Times -->
        <div class="p-3 rounded-xl bg-white/[0.03] border border-white/5 mb-4 space-y-1.5 text-xs text-slate-300">
          <div class="flex items-center justify-between">
            <span class="text-slate-400 flex items-center gap-1">
              <svg class="w-3.5 h-3.5 text-brand-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
              </svg>
              Departure Date:
            </span>
            <span class="font-semibold text-white">${depDateFormatted || "Scheduled"}</span>
          </div>

          <div class="flex items-center justify-between">
            <span class="text-slate-400">Time &amp; Duration:</span>
            <span class="font-medium text-white">
              ${depTimeFormatted} → ${arrTimeFormatted} ${durationFormatted ? `<span class="text-slate-400 text-[11px]">(${durationFormatted})</span>` : ""}
            </span>
          </div>

          <div class="flex items-center justify-between">
            <span class="text-slate-400">Route Type:</span>
            <span class="font-medium ${journey.total_stops === 0 ? "text-emerald-400" : "text-amber-300"}">
              ${stopsLabel} ${layovers.length > 0 ? `via ${layovers.join(", ")}` : ""}
            </span>
          </div>
        </div>

        <!-- Multi-leg Journey breakdown if multiple legs -->
        ${legs.length > 1 ? `
          <div class="mb-5 p-2.5 rounded-xl bg-white/[0.02] border border-white/5 space-y-1.5">
            <p class="text-[10px] uppercase font-bold tracking-wider text-slate-400 mb-1">Journey Legs (${legs.length} Flights)</p>
            ${legs.map((leg, i) => `
              <div class="flex items-center justify-between text-[11px] text-slate-300 bg-white/[0.02] px-2 py-1.5 rounded-lg">
                <span class="flex items-center gap-1.5">
                  <span class="w-4 h-4 rounded-full bg-brand-500/20 text-brand-300 text-[10px] font-bold flex items-center justify-center">${i + 1}</span>
                  <span class="font-semibold text-white">${leg.source} → ${leg.destination}</span>
                  <span class="text-slate-400 text-[10px]">(#${leg.flight_id})</span>
                  ${(leg.status && leg.status.toLowerCase().includes("wait")) ? `<span class="px-1.5 py-0.5 text-[9px] font-bold text-amber-300 bg-amber-500/20 border border-amber-400/30 rounded">WL-${leg.current_position || "1"}</span>` : ""}
                </span>
                <span class="text-slate-400 font-mono text-[10px]">${formatTime(leg.departure_time)}</span>
              </div>
            `).join("")}
          </div>
        ` : ""}
      </div>

      <!-- Action Footer: Combined Price and Actions -->
      <div class="pt-3 border-t border-white/5 space-y-3 mt-auto">
        <div class="flex items-center justify-between text-xs">
          <span class="text-slate-400">Total Price:</span>
          <span class="text-base font-extrabold text-brand-300">₹${Number(journey.total_price || 0).toLocaleString()}</span>
        </div>

        ${!isHistory ? `
          <button
            id="btn-cancel-${pnr}"
            onclick="cancelJourney('${pnr}', this)"
            class="w-full py-2.5 text-xs font-semibold text-rose-300 hover:text-white border border-rose-500/25 bg-rose-500/10 hover:bg-rose-500/25 hover:border-rose-500/50 rounded-xl transition-all duration-200 flex items-center justify-center gap-2 focus:outline-none shadow-sm"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
            Cancel Journey
          </button>
        ` : `
          <div class="py-2 text-center text-xs text-slate-500 font-medium">
            ${journey.status === "cancelled" ? "✕ Cancelled Booking" : "✓ Completed Journey"}
          </div>
        `}
      </div>

    </div>
  `;
}

// ── Section Empty States ─────────────────────────────────
function renderEmptySection(type) {
  const configs = {
    upcoming: {
      icon: `<svg class="w-8 h-8 text-slate-500" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.125A59.768 59.768 0 0121.485 12 59.768 59.768 0 013.27 20.875L5.999 12zm0 0h7.5"/></svg>`,
      text: "No active upcoming journeys.",
      action: `<a href="index.html" class="mt-2 px-4 py-2 text-xs font-semibold text-white bg-gradient-to-r from-brand-600 to-brand-500 rounded-lg hover:from-brand-500 hover:to-brand-400 transition-all shadow-md">Search Flights</a>`,
    },
    waitlist: {
      icon: `<svg class="w-8 h-8 text-amber-500/40" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
      text: "No tickets currently on waitlist.",
      action: `<p class="text-[11px] text-slate-500 mt-1">If flights fill up, waitlisted passengers are prioritized via Min-Heap.</p>`,
    },
    history: {
      icon: `<svg class="w-8 h-8 text-slate-600" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
      text: "No travel history records found.",
      action: "",
    },
  };

  const cfg = configs[type] || configs.upcoming;

  return `
    <div class="col-span-full flex flex-col items-center justify-center py-12 px-4 glass rounded-2xl border border-white/5 text-center">
      <div class="w-12 h-12 rounded-full bg-white/[0.03] flex items-center justify-center mb-3">
        ${cfg.icon}
      </div>
      <p class="text-sm text-slate-400 font-medium">${cfg.text}</p>
      ${cfg.action}
    </div>
  `;
}

// ── Render Entire Dashboard ──────────────────────────────
function renderDashboard(data) {
  const upcoming  = Array.isArray(data.upcoming_flights) ? data.upcoming_flights : [];
  const waitlist  = Array.isArray(data.waitlisted_tickets) ? data.waitlisted_tickets : [];
  const history   = Array.isArray(data.past_flights) ? data.past_flights : [];

  // Update counters
  if (countActiveEl)   countActiveEl.textContent   = upcoming.length;
  if (countWaitlistEl) countWaitlistEl.textContent = waitlist.length;
  if (countHistoryEl)  countHistoryEl.textContent  = history.length;

  if (badgeActiveEl)   badgeActiveEl.textContent   = `${upcoming.length} ${upcoming.length === 1 ? "Journey" : "Journeys"}`;
  if (badgeWaitlistEl) badgeWaitlistEl.textContent = `${waitlist.length} In Queue`;
  if (badgeHistoryEl)  badgeHistoryEl.textContent  = `${history.length} ${history.length === 1 ? "Record" : "Records"}`;

  // Render Section 1: Active Itineraries
  if (upcomingContainer) {
    upcomingContainer.innerHTML = upcoming.length > 0
      ? upcoming.map((j, i) => buildJourneyCard(j, "upcoming", i)).join("")
      : renderEmptySection("upcoming");
  }

  // Render Section 2: Waitlist Tracker
  if (waitlistContainer) {
    waitlistContainer.innerHTML = waitlist.length > 0
      ? waitlist.map((j, i) => buildJourneyCard(j, "waitlist", i)).join("")
      : renderEmptySection("waitlist");
  }

  // Render Section 3: Travel History
  if (historyContainer) {
    historyContainer.innerHTML = history.length > 0
      ? history.map((j, i) => buildJourneyCard(j, "history", i)).join("")
      : renderEmptySection("history");
  }
}

// ── Cancel Journey by PNR ────────────────────────────────
async function cancelJourney(pnr, btn) {
  if (!confirm(`Are you sure you want to cancel journey PNR #${pnr}? Any held seats will be freed and waitlisted passengers promoted.`)) {
    return;
  }

  // Prevent multiple clicks
  btn.disabled = true;
  const originalHTML = btn.innerHTML;
  btn.innerHTML = `
    <span class="flex items-center gap-1.5">
      <svg class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
      </svg>
      Cancelling…
    </span>
  `;

  try {
    const resp = await fetchWithAuth(`/bookings/${encodeURIComponent(pnr)}`, {
      method: "DELETE",
    });

    if (resp.status === 401) return; // fetchWithAuth redirects on 401

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || "Failed to cancel journey. Please try again.", "error");
      btn.disabled = false;
      btn.innerHTML = originalHTML;
      return;
    }

    const data = await resp.json().catch(() => ({}));
    const promotedCount = Array.isArray(data.promoted_passengers) ? data.promoted_passengers.length : 0;
    const toastMsg = promotedCount > 0
      ? `Journey #${pnr} cancelled. Freed seat allocated to waitlist passenger via Min-Heap!`
      : `Journey #${pnr} cancelled successfully.`;

    showToast(toastMsg, "success");

    // Dynamically remove the journey card from the DOM without full page reload
    const card = document.getElementById(`journey-card-${pnr}`);
    if (card) {
      const parentContainer = card.parentElement;
      card.classList.add("card-removing");

      setTimeout(() => {
        card.remove();

        // Update counts in real time
        if (parentContainer === upcomingContainer) {
          const current = parseInt(countActiveEl.textContent, 10) || 1;
          const next = Math.max(0, current - 1);
          countActiveEl.textContent = next;
          badgeActiveEl.textContent = `${next} ${next === 1 ? "Journey" : "Journeys"}`;
          if (upcomingContainer.children.length === 0) {
            upcomingContainer.innerHTML = renderEmptySection("upcoming");
          }
        } else if (parentContainer === waitlistContainer) {
          const current = parseInt(countWaitlistEl.textContent, 10) || 1;
          const next = Math.max(0, current - 1);
          countWaitlistEl.textContent = next;
          badgeWaitlistEl.textContent = `${next} In Queue`;
          if (waitlistContainer.children.length === 0) {
            waitlistContainer.innerHTML = renderEmptySection("waitlist");
          }
        }
      }, 360);
    }
  } catch (err) {
    console.error("Cancel journey error:", err);
    showToast("Could not reach server. Please check backend connection.", "error");
    btn.disabled = false;
    btn.innerHTML = originalHTML;
  }
}

// ── Load Dashboard on Page Startup ───────────────────────
async function loadDashboard() {
  const loadingHTML = `
    <div class="col-span-full flex flex-col items-center justify-center py-16 gap-3">
      <div class="spinner"></div>
      <p class="text-xs text-slate-400 animate-pulse">Loading journey records…</p>
    </div>
  `;

  if (upcomingContainer) upcomingContainer.innerHTML = loadingHTML;
  if (waitlistContainer) waitlistContainer.innerHTML = loadingHTML;
  if (historyContainer)  historyContainer.innerHTML  = loadingHTML;

  try {
    const resp = await fetchWithAuth("/dashboard");
    if (resp.status === 401) return; // fetchWithAuth handles redirect

    if (!resp.ok) {
      throw new Error(`Server returned HTTP ${resp.status}`);
    }

    const data = await resp.json();
    renderDashboard(data);
  } catch (err) {
    console.error("Load dashboard error:", err);
    const errorHTML = `
      <div class="col-span-full flex flex-col items-center justify-center py-12 gap-2 text-center">
        <p class="text-xs text-rose-400">Failed to load journeys. Please ensure backend is running.</p>
        <button onclick="loadDashboard()" class="text-[11px] text-brand-300 underline mt-1">Try again</button>
      </div>
    `;
    if (upcomingContainer) upcomingContainer.innerHTML = errorHTML;
    if (waitlistContainer) waitlistContainer.innerHTML = errorHTML;
    if (historyContainer)  historyContainer.innerHTML  = errorHTML;
  }
}

// ── Logout ────────────────────────────────────────────────
if (logoutBtn && typeof logoutBtn.addEventListener === "function") {
  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("token");
    window.location.href = "index.html";
  });
}

// ── Initialize on page load ──────────────────────────────
loadDashboard();
