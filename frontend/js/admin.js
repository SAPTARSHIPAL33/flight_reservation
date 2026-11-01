// ═══════════════════════════════════════════════════════
//  admin.js — AeroBook Admin Portal Controller
// ═══════════════════════════════════════════════════════

// ── Auth Guard ───────────────────────────────────────────
const token = localStorage.getItem("token");
if (!token) {
  window.location.replace("login.html");
}

// ── DOM References ───────────────────────────────────────
const toastEl = document.getElementById("toast");
const adminNameTag = document.getElementById("admin-name-tag");
const btnRefresh = document.getElementById("btn-refresh");
const btnLogout = document.getElementById("btn-logout");

// Stats elements
const statFlights = document.getElementById("stat-flights");
const statAirports = document.getElementById("stat-airports");
const statUsers = document.getElementById("stat-users");
const statBookings = document.getElementById("stat-bookings");
const statConfirmed = document.getElementById("stat-confirmed");
const statWaitlist = document.getElementById("stat-waitlist");

// Tables
const flightsTableBody = document.getElementById("flights-table-body");
const airportsTableBody = document.getElementById("airports-table-body");
const bookingsTableBody = document.getElementById("bookings-table-body");

// Tabs
const tabButtons = document.querySelectorAll(".tab-btn");
const tabContents = document.querySelectorAll(".tab-content");

// Modals
const flightModal = document.getElementById("flight-modal");
const flightForm = document.getElementById("flight-form");
const flightModalTitle = document.getElementById("flight-modal-title");
const btnOpenCreateFlight = document.getElementById("btn-open-create-flight");
const btnCloseFlightModal = document.getElementById("btn-close-flight-modal");
const btnCancelFlight = document.getElementById("btn-cancel-flight");

const airportModal = document.getElementById("airport-modal");
const airportForm = document.getElementById("airport-form");
const btnOpenCreateAirport = document.getElementById("btn-open-create-airport");
const btnCloseAirportModal = document.getElementById("btn-close-airport-modal");
const btnCancelAirport = document.getElementById("btn-cancel-airport");

// State caches
let currentFlights = [];
let currentAirports = [];

// ── Toast Notification ───────────────────────────────────
let toastTimer;
function showToast(message, type = "success") {
  if (!toastEl) return;
  toastEl.textContent = message;
  toastEl.className = [
    "fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl text-sm font-semibold shadow-2xl transition-all duration-300",
    type === "success"
      ? "bg-emerald-500/90 text-white border border-emerald-400/40"
      : "bg-red-500/90 text-white border border-red-400/40",
  ].join(" ");
  toastEl.style.opacity = "1";
  toastEl.style.transform = "translateY(0)";

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastEl.style.opacity = "0";
    toastEl.style.transform = "translateY(12px)";
  }, 3500);
}

// ── Verify Admin Role on Startup ─────────────────────────
async function verifyAdmin() {
  try {
    const resp = await fetchWithAuth("/user/me");
    if (!resp || resp.status === 401) return;

    if (!resp.ok) {
      window.location.replace("login.html");
      return;
    }

    const user = await resp.json();
    if (user.role !== "admin") {
      alert("Access denied. Admin role required.");
      window.location.replace("index.html");
      return;
    }

    if (adminNameTag) {
      adminNameTag.textContent = user.name || "Admin";
    }
  } catch (err) {
    console.error("Admin verification error:", err);
  }
}

// ── Load Stats ───────────────────────────────────────────
async function loadStats() {
  try {
    const resp = await fetchWithAuth("/admin/stats");
    if (!resp || !resp.ok) return;

    const data = await resp.json();
    if (statFlights) statFlights.textContent = data.total_flights ?? 0;
    if (statAirports) statAirports.textContent = data.total_airports ?? 0;
    if (statUsers) statUsers.textContent = data.total_users ?? 0;
    if (statBookings) statBookings.textContent = data.total_bookings ?? 0;
    if (statConfirmed) statConfirmed.textContent = data.active_bookings ?? 0;
    if (statWaitlist) statWaitlist.textContent = data.waiting_bookings ?? 0;
  } catch (err) {
    console.error("Stats loading error:", err);
  }
}

// ── Load Flights ─────────────────────────────────────────
async function loadFlights() {
  try {
    const resp = await fetchWithAuth("/admin/flights");
    if (!resp || !resp.ok) {
      flightsTableBody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-red-400">Failed to load flights</td></tr>`;
      return;
    }

    const flights = await resp.json();
    currentFlights = flights;

    if (!flights || flights.length === 0) {
      flightsTableBody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-slate-400">No flights registered in the database</td></tr>`;
      return;
    }

    flightsTableBody.innerHTML = flights.map((f) => {
      const dep = f.departure_time ? new Date(f.departure_time).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "-";
      const arr = f.arrival_time ? new Date(f.arrival_time).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "-";
      const hasSeats = f.seats_available > 0;

      return `
        <tr class="hover:bg-white/[0.03] transition-colors">
          <td class="py-3 px-4 font-mono font-bold text-amber-300">#${f.flight_id}</td>
          <td class="py-3 px-4">
            <span class="font-bold text-white">${f.source}</span>
            <span class="text-slate-400 mx-1">→</span>
            <span class="font-bold text-white">${f.destination}</span>
          </td>
          <td class="py-3 px-4 text-slate-300">${dep}</td>
          <td class="py-3 px-4 text-slate-300">${arr}</td>
          <td class="py-3 px-4 font-semibold text-white">₹${Number(f.price).toLocaleString()}</td>
          <td class="py-3 px-4">
            <span class="px-2.5 py-0.5 text-xs font-semibold rounded-full ${
              hasSeats
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                : "bg-amber-500/15 text-amber-300 border border-amber-500/30"
            }">
              ${hasSeats ? `${f.seats_available} left` : "Full (0 seats)"}
            </span>
          </td>
          <td class="py-3 px-4 text-right">
            <div class="flex items-center justify-end gap-2">
              <button onclick="openEditFlight(${f.flight_id})" class="px-2.5 py-1 text-xs font-medium text-slate-200 hover:text-white glass rounded-lg hover:border-amber-400/50 transition-all">
                Edit
              </button>
              <button onclick="deleteFlight(${f.flight_id})" class="px-2.5 py-1 text-xs font-medium text-red-300 hover:text-red-100 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg transition-all">
                Delete
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Flights loading error:", err);
  }
}

// ── Load Airports ────────────────────────────────────────
async function loadAirports() {
  try {
    const resp = await fetchWithAuth("/admin/airports");
    if (!resp || !resp.ok) {
      airportsTableBody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-red-400">Failed to load airports</td></tr>`;
      return;
    }

    const airports = await resp.json();
    currentAirports = airports;

    if (!airports || airports.length === 0) {
      airportsTableBody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-slate-400">No airports registered</td></tr>`;
      return;
    }

    airportsTableBody.innerHTML = airports.map((a) => `
      <tr class="hover:bg-white/[0.03] transition-colors">
        <td class="py-3 px-4 text-slate-400 font-mono text-xs">#${a.id}</td>
        <td class="py-3 px-4 font-mono font-bold text-brand-300 text-base">${a.place}</td>
        <td class="py-3 px-4 font-semibold text-white">${a.name}</td>
        <td class="py-3 px-4 font-mono text-xs text-slate-300">${a.latitude}, ${a.longitude}</td>
        <td class="py-3 px-4 text-right">
          <button onclick="deleteAirport(${a.id})" class="px-2.5 py-1 text-xs font-medium text-red-300 hover:text-red-100 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg transition-all">
            Delete
          </button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Airports loading error:", err);
  }
}

// ── Load Bookings ────────────────────────────────────────
async function loadBookings() {
  try {
    const resp = await fetchWithAuth("/admin/bookings");
    if (!resp || !resp.ok) {
      bookingsTableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-red-400">Failed to load bookings</td></tr>`;
      return;
    }

    const bookings = await resp.json();

    if (!bookings || bookings.length === 0) {
      bookingsTableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-slate-400">No bookings made yet</td></tr>`;
      return;
    }

    bookingsTableBody.innerHTML = bookings.map((b) => {
      const dt = b.created_at ? new Date(b.created_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "-";

      let statusBadge = "";
      if (b.status === "confirmed") {
        statusBadge = `<span class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">✓ Confirmed</span>`;
      } else if (b.status === "waiting_list") {
        statusBadge = `<span class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">⏳ Waitlist</span>`;
      } else {
        statusBadge = `<span class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-red-500/15 text-red-300 border border-red-500/30">✕ Cancelled</span>`;
      }

      return `
        <tr class="hover:bg-white/[0.03] transition-colors">
          <td class="py-3 px-4 font-mono font-bold text-white">#${b.booking_id}</td>
          <td class="py-3 px-4">
            <p class="font-medium text-white">${b.passenger_name}</p>
            <p class="text-xs text-slate-400">${b.passenger_email || `ID #${b.passenger_id}`}</p>
          </td>
          <td class="py-3 px-4 font-mono text-amber-300">#${b.flight_id}</td>
          <td class="py-3 px-4 font-semibold text-slate-200">${b.flight_source} → ${b.flight_destination}</td>
          <td class="py-3 px-4">${statusBadge}</td>
          <td class="py-3 px-4 text-xs text-slate-400">${dt}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Bookings loading error:", err);
  }
}

// ── Tab Switching ────────────────────────────────────────
tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabButtons.forEach((b) => {
      b.classList.remove("active");
      b.classList.add("text-slate-400");
    });
    btn.classList.add("active");
    btn.classList.remove("text-slate-400");

    const tabName = btn.dataset.tab;
    tabContents.forEach((c) => {
      if (c.id === `tab-content-${tabName}`) {
        c.classList.remove("hidden");
      } else {
        c.classList.add("hidden");
      }
    });

    if (tabName === "flights") loadFlights();
    if (tabName === "airports") loadAirports();
    if (tabName === "bookings") loadBookings();
  });
});

// ── Create & Edit Flight Modal Logic ─────────────────────
function openCreateFlight() {
  flightModalTitle.textContent = "Add New Flight";
  document.getElementById("flight-form-id").value = "";
  document.getElementById("flight-form-source").value = "";
  document.getElementById("flight-form-source").disabled = false;
  document.getElementById("flight-form-destination").value = "";
  document.getElementById("flight-form-destination").disabled = false;
  document.getElementById("flight-form-distance").value = "1000";
  document.getElementById("flight-form-price").value = "5000";

  // Default times
  const now = new Date();
  const dep = new Date(now.getTime() + 24 * 3600 * 1000);
  const arr = new Date(dep.getTime() + 2 * 3600 * 1000);
  document.getElementById("flight-form-departure").value = dep.toISOString().slice(0, 16);
  document.getElementById("flight-form-arrival").value = arr.toISOString().slice(0, 16);
  document.getElementById("flight-form-seats").value = "50";

  flightModal.classList.remove("hidden");
  flightModal.classList.add("flex");
}

function openEditFlight(flightId) {
  const flight = currentFlights.find((f) => f.flight_id === flightId);
  if (!flight) return;

  flightModalTitle.textContent = `Edit Flight #${flight.flight_id}`;
  document.getElementById("flight-form-id").value = flight.flight_id;
  document.getElementById("flight-form-source").value = flight.source;
  document.getElementById("flight-form-source").disabled = true;
  document.getElementById("flight-form-destination").value = flight.destination;
  document.getElementById("flight-form-destination").disabled = true;
  document.getElementById("flight-form-distance").value = flight.distance || 1000;
  document.getElementById("flight-form-price").value = flight.price;

  if (flight.departure_time) {
    document.getElementById("flight-form-departure").value = new Date(flight.departure_time).toISOString().slice(0, 16);
  }
  if (flight.arrival_time) {
    document.getElementById("flight-form-arrival").value = new Date(flight.arrival_time).toISOString().slice(0, 16);
  }
  document.getElementById("flight-form-seats").value = flight.seats_available;

  flightModal.classList.remove("hidden");
  flightModal.classList.add("flex");
}

function closeFlightModal() {
  flightModal.classList.add("hidden");
  flightModal.classList.remove("flex");
}

btnOpenCreateFlight?.addEventListener("click", openCreateFlight);
btnCloseFlightModal?.addEventListener("click", closeFlightModal);
btnCancelFlight?.addEventListener("click", closeFlightModal);

flightForm?.addEventListener("submit", async (e) => {
  e.preventDefault();

  const flightId = document.getElementById("flight-form-id").value;
  const source = document.getElementById("flight-form-source").value.trim().toUpperCase();
  const destination = document.getElementById("flight-form-destination").value.trim().toUpperCase();
  const distance = parseFloat(document.getElementById("flight-form-distance").value);
  const price = parseFloat(document.getElementById("flight-form-price").value);
  const departure_time = document.getElementById("flight-form-departure").value;
  const arrival_time = document.getElementById("flight-form-arrival").value;
  const seats_available = parseInt(document.getElementById("flight-form-seats").value, 10);

  const isEdit = Boolean(flightId);

  try {
    let resp;
    if (isEdit) {
      // PUT /admin/flights/{id}
      resp = await fetchWithAuth(`/admin/flights/${flightId}`, {
        method: "PUT",
        body: JSON.stringify({
          price,
          seats_available,
          departure_time: new Date(departure_time).toISOString(),
          arrival_time: new Date(arrival_time).toISOString(),
        }),
      });
    } else {
      // POST /admin/flights
      resp = await fetchWithAuth("/admin/flights", {
        method: "POST",
        body: JSON.stringify({
          source,
          destination,
          distance,
          price,
          departure_time: new Date(departure_time).toISOString(),
          arrival_time: new Date(arrival_time).toISOString(),
          seats_available,
        }),
      });
    }

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || "Flight operation failed.", "error");
      return;
    }

    showToast(isEdit ? "Flight updated successfully." : "New flight added to route inventory.");
    closeFlightModal();
    loadFlights();
    loadStats();
  } catch (err) {
    console.error("Flight save error:", err);
    showToast("Error saving flight.", "error");
  }
});

async function deleteFlight(flightId) {
  if (!confirm(`Are you sure you want to delete Flight #${flightId}? This route will be removed from shortest path calculations.`)) return;

  try {
    const resp = await fetchWithAuth(`/admin/flights/${flightId}`, { method: "DELETE" });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || "Could not delete flight.", "error");
      return;
    }

    showToast(`Flight #${flightId} deleted.`);
    loadFlights();
    loadStats();
  } catch (err) {
    console.error("Delete flight error:", err);
    showToast("Error deleting flight.", "error");
  }
}

// ── Create & Delete Airport Modal Logic ───────────────────
function openCreateAirport() {
  document.getElementById("airport-form-place").value = "";
  document.getElementById("airport-form-name").value = "";
  document.getElementById("airport-form-lat").value = "";
  document.getElementById("airport-form-lon").value = "";

  airportModal.classList.remove("hidden");
  airportModal.classList.add("flex");
}

function closeAirportModal() {
  airportModal.classList.add("hidden");
  airportModal.classList.remove("flex");
}

btnOpenCreateAirport?.addEventListener("click", openCreateAirport);
btnCloseAirportModal?.addEventListener("click", closeAirportModal);
btnCancelAirport?.addEventListener("click", closeAirportModal);

airportForm?.addEventListener("submit", async (e) => {
  e.preventDefault();

  const place = document.getElementById("airport-form-place").value.trim().toUpperCase();
  const name = document.getElementById("airport-form-name").value.trim();
  const latitude = parseFloat(document.getElementById("airport-form-lat").value);
  const longitude = parseFloat(document.getElementById("airport-form-lon").value);

  try {
    const resp = await fetchWithAuth("/admin/airports", {
      method: "POST",
      body: JSON.stringify({ place, name, latitude, longitude }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || "Could not register airport.", "error");
      return;
    }

    showToast(`Airport ${place} registered successfully.`);
    closeAirportModal();
    loadAirports();
    loadStats();
  } catch (err) {
    console.error("Airport save error:", err);
    showToast("Error saving airport.", "error");
  }
});

async function deleteAirport(airportId) {
  if (!confirm(`Are you sure you want to remove this airport node?`)) return;

  try {
    const resp = await fetchWithAuth(`/admin/airports/${airportId}`, { method: "DELETE" });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || "Could not remove airport.", "error");
      return;
    }

    showToast("Airport removed.");
    loadAirports();
    loadStats();
  } catch (err) {
    console.error("Delete airport error:", err);
    showToast("Error removing airport.", "error");
  }
}

// ── Refresh & Logout ─────────────────────────────────────
btnRefresh?.addEventListener("click", () => {
  loadStats();
  loadFlights();
  loadAirports();
  loadBookings();
  showToast("Dashboard refreshed.");
});

btnLogout?.addEventListener("click", () => {
  localStorage.removeItem("token");
  localStorage.removeItem("role");
  localStorage.removeItem("userName");
  window.location.href = "login.html";
});

// Expose globals for onclick in generated HTML
window.openEditFlight = openEditFlight;
window.deleteFlight = deleteFlight;
window.deleteAirport = deleteAirport;

// ── Kick off ─────────────────────────────────────────────
(async function init() {
  await verifyAdmin();
  loadStats();
  loadFlights();
})();
