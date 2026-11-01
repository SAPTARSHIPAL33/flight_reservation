// ═══════════════════════════════════════════════════════
//  search.js — Flight Search & Booking (Direct & Multi-Leg)
// ═══════════════════════════════════════════════════════

var API_BASE = (typeof window !== "undefined" && window.API_BASE)
  ? window.API_BASE
  : ((typeof window !== "undefined" && (window.location.protocol === "http:" || window.location.protocol === "https:") && window.location.port === "8000")
      ? window.location.origin
      : "http://127.0.0.1:8000");

// ── DOM references ──────────────────────────────────────
const searchForm = document.getElementById("search-form");
const resultsContainer = document.getElementById("results-container");

// ── Book flight(s) ──────────────────────────────────────
/**
 * Called when the user clicks "Book Now" or "Join Waitlist".
 * If not logged in → redirect to login.
 * If logged in     → POST /book with an array of flight_ids.
 *
 * @param {number|number[]} flightIds — array of flight IDs (or single ID)
 * @param {HTMLButtonElement} btn
 */
async function bookFlight(flightIds, btn) {
  // Support comma-separated string (e.g. "20,28"), array of numbers, or single ID
  let ids;
  if (typeof flightIds === "string") {
    ids = flightIds.split(",").map((id) => parseInt(id.trim(), 10)).filter(Boolean);
  } else if (Array.isArray(flightIds)) {
    ids = flightIds.map((id) => parseInt(id, 10)).filter(Boolean);
  } else {
    ids = [parseInt(flightIds, 10)].filter(Boolean);
  }

  const token = localStorage.getItem("token");

  // Not logged in — send to login page
  if (!token) {
    window.location.href = "login.html";
    return;
  }

  // Already processed
  if (btn.disabled) return;

  const originalHTML = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `
    <span class="flex items-center justify-center gap-2">
      <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
      </svg>
      Booking…
    </span>`;

  try {
    const resp = await fetch(`${API_BASE}/book`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
      },
      body: JSON.stringify({ flight_ids: ids }),
    });

    // Token expired or invalid
    if (resp.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "login.html";
      return;
    }

    const data = await resp.json().catch(() => ({}));

    if (!resp.ok) {
      const errorMsg = data.detail || (typeof data === "string" ? data : "Booking failed. Please try again.");
      console.error("Booking error details:", data);
      alert(errorMsg);
      btn.disabled = false;
      btn.innerHTML = originalHTML;
      return;
    }

    // Success — check if any ticket is waiting_list or pending
    const bookings = Array.isArray(data) ? data : [data];
    const isWaitlist = bookings.some((b) => b?.status === "waiting_list" || b?.status === "pending");
    const assignedWl = bookings.find((b) => b?.waitlist_position)?.waitlist_position;
    const wlText = assignedWl ? ` (WL-${assignedWl})` : "";

    btn.innerHTML = isWaitlist
      ? `⏳ Added to Waitlist${wlText}! View in Dashboard`
      : `✓ Booked! Go to Dashboard`;
    btn.className = btn.className
      .replace(/from-\S+/g, "")
      .replace(/to-\S+/g, "")
      .replace(/hover:from-\S+/g, "")
      .replace(/hover:to-\S+/g, "");
    btn.classList.add(
      isWaitlist ? "bg-amber-600" : "bg-emerald-600"
    );

    // Replace the button's click behavior to cleanly navigate to the dashboard
    btn.onclick = (e) => {
      if (e) e.stopPropagation();
      window.location.href = "dashboard.html";
    };
    btn.disabled = false; // allow click to go to dashboard
  } catch (err) {
    console.error("Booking error:", err);
    alert("Could not reach the server. Make sure the backend is running.");
    btn.disabled = false;
    btn.innerHTML = originalHTML;
  }
}

// ── Render helpers ──────────────────────────────────────

/**
 * Show a centered status message (loading / error / empty).
 * @param {"loading"|"error"|"empty"} type
 * @param {string} [message]
 */
function showStatus(type, message) {
  const templates = {
    loading: `
      <div class="flex flex-col items-center justify-center py-20 gap-4">
        <div class="spinner"></div>
        <p class="text-sm text-surface-200/60 animate-pulse">Searching for all available routes&hellip;</p>
      </div>`,
    error: `
      <div class="flex flex-col items-center justify-center py-20 gap-3 text-center">
        <div class="w-14 h-14 rounded-full bg-red-500/10 flex items-center justify-center">
          <svg class="w-7 h-7 text-red-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
        </div>
        <p class="text-sm text-red-300">${message || "Something went wrong. Please try again."}</p>
      </div>`,
    empty: `
      <div class="flex flex-col items-center justify-center py-20 gap-3 text-center">
        <div class="w-14 h-14 rounded-full bg-surface-200/5 flex items-center justify-center">
          <svg class="w-7 h-7 text-surface-200/30" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.125A59.768 59.768 0 0121.485 12 59.768 59.768 0 013.27 20.875L5.999 12zm0 0h7.5"/>
          </svg>
        </div>
        <p class="text-sm text-surface-200/50">No flights found for this route.</p>
        <p class="text-xs text-surface-200/30">Try a different source or destination.</p>
      </div>`,
  };

  resultsContainer.innerHTML = templates[type] || "";
}

/**
 * Format a datetime string into readable time (HH:MM).
 * @param {string} dtStr
 * @returns {string}
 */
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

/**
 * Calculate human-readable duration between departure and arrival.
 * @param {string} startStr
 * @param {string} endStr
 * @returns {string} e.g. "2h 45m" or "1d 3h"
 */
function formatDuration(startStr, endStr) {
  if (!startStr || !endStr) return "";
  try {
    const start = new Date(startStr);
    const end = new Date(endStr);
    const diffMs = end.getTime() - start.getTime();
    if (isNaN(diffMs) || diffMs <= 0) return "";
    const totalMinutes = Math.floor(diffMs / 60000);
    const days = Math.floor(totalMinutes / (24 * 60));
    const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
    const mins = totalMinutes % 60;
    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0 || days > 0) parts.push(`${hours}h`);
    if (mins > 0 || parts.length === 0) parts.push(`${mins}m`);
    return parts.join(" ");
  } catch (e) {
    return "";
  }
}

/**
 * Render the visual connector line between origin and destination:
 * - Direct (total_stops === 0): continuous unbroken direct line with airplane icon.
 * - Indirect (total_stops > 0): segmented connector line featuring circular badges with intermediate layover airport codes.
 *
 * @param {number} totalStops
 * @param {Array} legs
 * @returns {string} HTML string
 */
function renderConnector(totalStops, legs) {
  if (totalStops === 0) {
    // Direct flight: continuous unbroken direct line with plane icon
    return `
      <div class="flex-1 flex items-center px-2">
        <div class="flex-1 h-0.5 bg-gradient-to-r from-emerald-500/40 via-emerald-400 to-emerald-500/40"></div>
        <div class="w-7 h-7 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shrink-0 mx-1 shadow-sm" title="Direct Flight">
          <svg class="w-3.5 h-3.5 text-emerald-400" fill="currentColor" viewBox="0 0 24 24">
            <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/>
          </svg>
        </div>
        <div class="flex-1 h-0.5 bg-gradient-to-r from-emerald-500/40 via-emerald-400 to-emerald-500/40"></div>
      </div>
    `;
  }

  // Indirect flight (total_stops > 0):
  // Segmented connector line with circular badges for intermediate layover airport codes
  const layovers = [];
  if (Array.isArray(legs) && legs.length > 1) {
    for (let i = 0; i < legs.length - 1; i++) {
      if (legs[i].destination) {
        layovers.push(legs[i].destination);
      }
    }
  }

  if (layovers.length === 0) {
    return `
      <div class="flex-1 flex items-center px-2">
        <div class="flex-1 h-0.5 bg-amber-500/40 border-t border-dashed border-amber-400/60"></div>
        <div class="w-7 h-7 rounded-full bg-amber-500/20 border border-amber-400/50 flex items-center justify-center shrink-0 mx-1 text-[10px] font-bold text-amber-200 shadow-sm" title="Layover">
          Stop
        </div>
        <div class="flex-1 h-0.5 bg-amber-500/40 border-t border-dashed border-amber-400/60"></div>
      </div>
    `;
  }

  const segmentsHtml = layovers.map((code) => `
    <div class="flex-1 h-0.5 bg-amber-500/30 border-t border-dashed border-amber-400/50"></div>
    <div class="w-7 h-7 rounded-full bg-amber-500/20 border border-amber-400/60 flex items-center justify-center shrink-0 text-[10px] font-bold text-amber-200 shadow-sm" title="Layover at ${code}">
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

/**
 * Build a single itinerary/flight card element.
 * Parses the itinerary schema: { legs: [...], total_stops: int, ... }
 *
 * @param {Object} itinerary
 * @param {number} index — used to stagger entrance animation
 * @returns {string} HTML string
 */
function buildFlightCard(itinerary, index) {
  // Normalize legs array
  const legs = Array.isArray(itinerary.legs) && itinerary.legs.length > 0
    ? itinerary.legs
    : [{
        flight_id: itinerary.flight_id,
        source: itinerary.source,
        destination: itinerary.destination,
        departure_time: itinerary.departure_time || itinerary.depart_time,
        arrival_time: itinerary.arrival_time,
        price: itinerary.price,
        seats_available: itinerary.seats_available,
      }];

  const totalStops = itinerary.total_stops !== undefined
    ? itinerary.total_stops
    : Math.max(0, legs.length - 1);

  const isDirect = totalStops === 0;

  // Extract all associated flight IDs for multi-leg booking
  const flightIds = legs.map((l) => l.flight_id).filter(Boolean);

  // Available seats & waitlist queue length
  const minSeats = itinerary.seats_available !== undefined
    ? itinerary.seats_available
    : Math.min(...legs.map((l) => (l.seats_available !== undefined ? l.seats_available : 0)));

  const currentWaitlistLength = itinerary.current_waitlist_length !== undefined
    ? Number(itinerary.current_waitlist_length)
    : (Number(legs[0]?.current_waitlist_length) || 0);

  const nextWaitlistPosition = currentWaitlistLength + 1;
  const waitlistLabel = `Join Waitlist (WL-${nextWaitlistPosition})`;

  const hasSeats = minSeats > 0;
  const btnLabel = hasSeats ? "Book Now" : waitlistLabel;
  const btnClasses = hasSeats
    ? "bg-gradient-to-r from-brand-600 to-brand-500 hover:from-brand-500 hover:to-brand-400 shadow-brand-600/25"
    : "bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 shadow-amber-600/25";
  const seatColor = hasSeats ? "text-emerald-400" : "text-amber-400";

  // Route origin & destination
  const origin = itinerary.source || legs[0].source;
  const destination = itinerary.destination || legs[legs.length - 1].destination;

  // Total combined price of all legs
  const price = itinerary.total_price !== undefined
    ? itinerary.total_price
    : (itinerary.price !== undefined
        ? itinerary.price
        : legs.reduce((sum, l) => sum + (Number(l.price) || 0), 0));

  // Departure, arrival, and duration of all legs
  const depTime = itinerary.departure_time || legs[0].departure_time || legs[0].depart_time;
  const arrTime = itinerary.arrival_time || legs[legs.length - 1].arrival_time;
  const depTimeFormatted = formatTime(depTime);
  const arrTimeFormatted = formatTime(arrTime);
  const durationFormatted = formatDuration(depTime, arrTime);

  // Comma-separated string of all flight_ids for multi-leg booking
  const flightIdsStr = flightIds.join(",");

  // Check for badge (e.g. "Recommended" generated by Dijkstra fastest layover routing)
  const badgeText = itinerary.badge || (itinerary.is_fastest_layover ? "Recommended" : null);
  const isRecommended = Boolean(badgeText);

  return `
    <div class="flight-card group glass rounded-2xl p-6 transition-all duration-300 relative ${
      isRecommended
        ? "border-amber-400/60 shadow-xl shadow-amber-500/10 ring-1 ring-amber-400/40 hover:border-amber-400"
        : "hover:border-brand-500/30"
    }"
         style="animation-delay: ${index * 80}ms">

      <!-- Prominent "Recommended" Visual Badge if present -->
      ${badgeText ? `
        <div class="mb-3.5 -mt-1 flex items-center justify-between">
          <span class="inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-extrabold uppercase tracking-wider text-amber-950 bg-gradient-to-r from-amber-300 via-amber-400 to-yellow-400 rounded-full shadow-md shadow-amber-500/25">
            <svg class="w-3.5 h-3.5 text-amber-950" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
            </svg>
            ${badgeText} — Optimal Layover
          </span>
          <span class="text-[10px] text-amber-300/80 font-semibold tracking-wide flex items-center gap-1">
            <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping"></span>
            Fastest via Dijkstra
          </span>
        </div>
      ` : ""}

      <!-- Top row: Flight ID/Type badge + stops tag + seats -->
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-brand-300 bg-brand-500/10 border border-brand-500/15 rounded-full">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14"/>
            </svg>
            ${isDirect ? `Flight #${flightIds[0]}` : `Multi-Leg (#${flightIds.join(", #")})`}
          </span>

          <span class="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-full ${
            isDirect
              ? "text-emerald-300 bg-emerald-500/15 border border-emerald-500/25"
              : (isRecommended ? "text-amber-200 bg-amber-500/25 border border-amber-400/40" : "text-amber-300 bg-amber-500/15 border border-amber-500/25")
          }">
            ${isDirect ? "Direct" : `${totalStops} Layover${totalStops > 1 ? "s" : ""}`}
          </span>
        </div>

        <span class="text-xs font-semibold ${seatColor}">
          ${hasSeats ? minSeats + " seat" + (minSeats > 1 ? "s" : "") + " left" : waitlistLabel}
        </span>
      </div>

      <!-- Route visualization (Origin, connector line with layover badges, Destination) -->
      <div class="flex items-center gap-3 mb-4">
        <!-- Origin -->
        <div class="flex-1 text-center">
          <p class="text-xl font-extrabold text-white">${origin}</p>
          <p class="text-[10px] uppercase tracking-wider text-surface-200/40 mt-0.5">Origin</p>
        </div>

        <!-- Connector line (direct unbroken or segmented with layover circular badges) -->
        ${renderConnector(totalStops, legs)}

        <!-- Destination -->
        <div class="flex-1 text-center">
          <p class="text-xl font-extrabold text-white">${destination}</p>
          <p class="text-[10px] uppercase tracking-wider text-surface-200/40 mt-0.5">Destination</p>
        </div>
      </div>

      <!-- Total Duration and Combined Price info -->
      <div class="flex items-center justify-between text-xs text-surface-200/70 mb-5 px-3 bg-white/[0.03] py-2.5 rounded-xl border border-white/5">
        <div>
          ${depTimeFormatted ? `<span class="text-white font-semibold">${depTimeFormatted}</span>` : ""}
          ${depTimeFormatted && arrTimeFormatted ? `<span class="mx-1.5 text-surface-200/40">→</span>` : ""}
          ${arrTimeFormatted ? `<span class="text-white font-semibold">${arrTimeFormatted}</span>` : ""}
          ${durationFormatted ? `<span class="ml-2 text-[11px] text-surface-200/50">(${durationFormatted})</span>` : ""}
        </div>
        <div class="text-right">
          <span class="text-[11px] text-surface-200/40 mr-1">Total:</span>
          <span class="text-base font-extrabold text-brand-300">₹${Number(price).toLocaleString()}</span>
        </div>
      </div>

      <!-- Multi-leg route breakdown -->
      ${!isDirect ? `
        <div class="mb-5 p-3 rounded-xl bg-white/[0.03] border ${isRecommended ? "border-amber-400/30" : "border-white/5"} space-y-2">
          <div class="flex items-center justify-between text-[10px] uppercase font-bold tracking-wider ${isRecommended ? "text-amber-300" : "text-surface-200/50"} mb-1">
            <span>Journey Legs (${legs.length} flights)</span>
            <span>${totalStops} Layover${totalStops > 1 ? "s" : ""}</span>
          </div>
          ${legs.map((leg, i) => {
            const legDep = formatTime(leg.departure_time);
            const legArr = formatTime(leg.arrival_time);
            return `
              <div class="flex items-center justify-between text-xs text-surface-200/80 bg-white/[0.02] p-2 rounded-lg">
                <span class="flex items-center gap-2">
                  <span class="w-4 h-4 rounded-full bg-brand-500/20 text-brand-300 text-[10px] font-bold flex items-center justify-center">${i + 1}</span>
                  <span class="font-medium text-white">${leg.source} → ${leg.destination}</span>
                  <span class="text-[11px] text-surface-200/40">(#${leg.flight_id})</span>
                  ${legDep && legArr ? `<span class="text-[11px] text-surface-200/50">${legDep}–${legArr}</span>` : ""}
                </span>
                <span class="font-semibold text-white">₹${Number(leg.price).toLocaleString()}</span>
              </div>
            `;
          }).join("")}
        </div>
      ` : ""}

      <!-- Action button (passes comma-separated string of all flight_ids to bookFlight) -->
      <button
        onclick="bookFlight('${flightIdsStr}', this)"
        class="btn-lift w-full py-3 text-sm font-semibold text-white rounded-xl shadow-lg ${btnClasses} focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-surface-900 transition-all"
      >
        ${btnLabel}
      </button>
    </div>`;
}

/**
 * Render an array of itinerary objects into the results container.
 * Parses the nested JSON structure.
 *
 * @param {Object[]|Object} itineraries — array or object containing itineraries
 */
function renderFlights(itineraries) {
  // Support array of itineraries, or { itineraries: [...] }, or { flights: [...] }
  const list = Array.isArray(itineraries)
    ? itineraries
    : (itineraries?.itineraries || itineraries?.flights || []);

  const count = list.length;
  if (count === 0) {
    showStatus("empty");
    return;
  }

  const directCount = list.filter((it) => (it.total_stops === 0 || (it.legs && it.legs.length === 1))).length;
  const indirectCount = count - directCount;

  let subtitle = `${count} ${count > 1 ? "routes" : "route"} found`;
  if (directCount > 0 && indirectCount > 0) {
    subtitle = `${directCount} Direct ${directCount > 1 ? "Flights" : "Flight"} + 1 Fastest Layover (Dijkstra)`;
  } else if (indirectCount > 0) {
    subtitle = `1 Fastest Indirect Flight (Dijkstra)`;
  } else if (directCount > 0) {
    subtitle = `${directCount} Direct ${directCount > 1 ? "Flights" : "Flight"}`;
  }

  const heading = `
    <div class="mb-8 flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-white">Available Flights & Itineraries</h2>
        <p class="text-sm text-surface-200/70 mt-1 flex items-center gap-2">
          <span class="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          ${subtitle}
        </p>
      </div>
    </div>`;

  const cards = list.map((itinerary, i) => buildFlightCard(itinerary, i)).join("");

  resultsContainer.innerHTML = `
    ${heading}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
      ${cards}
    </div>`;
}

// ── Search handler ──────────────────────────────────────

searchForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  let source = document.getElementById("source").value.trim();
  let destination = document.getElementById("destination").value.trim();

  // If user selected "Delhi (DEL)" from datalist, extract "DEL"
  const srcParen = source.match(/\(([A-Za-z]{3})\)/);
  if (srcParen) source = srcParen[1];
  const dstParen = destination.match(/\(([A-Za-z]{3})\)/);
  if (dstParen) destination = dstParen[1];

  if (!source || !destination) return;

  // Show loading state
  showStatus("loading");

  // Smooth-scroll to the results area
  resultsContainer.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const query = `source=${encodeURIComponent(source)}&destination=${encodeURIComponent(destination)}`;

    let resp = await fetch(`${API_BASE}/search?${query}`);

    if (resp.status === 404) {
      showStatus("empty");
      return;
    }

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Server responded with status ${resp.status}`);
    }

    const data = await resp.json();

    // Pass data into renderFlights which handles arrays or nested objects
    renderFlights(data);
  } catch (err) {
    console.error("Flight search failed:", err);
    showStatus(
      "error",
      err.message || "Could not reach the server. Please ensure FastAPI is running on port 8000."
    );
  }
});
