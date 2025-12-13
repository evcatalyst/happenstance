const state = {
  view: "restaurants",
  filter: "",
  layout: "cards",
  data: {
    restaurants: [],
    events: [],
    pairings: [],
    meta: {},
    branding: {},
  },
};

const qs = new URLSearchParams(window.location.search);
state.view = qs.get("view") || localStorage.getItem("hs_view") || "restaurants";
state.filter = qs.get("filter") || "";
state.layout = qs.get("layout") || "cards";

const viewButtons = document.querySelectorAll("button[data-view]");
const filterInput = document.getElementById("filter-input");
const layoutSelect = document.getElementById("layout-select");
const restaurantsContainer = document.getElementById("restaurants-view");
const eventsContainer = document.getElementById("events-view");
const pairedContainer = document.getElementById("paired-view");
const metaInfo = document.getElementById("meta-info");

filterInput.value = state.filter;
layoutSelect.value = state.layout;

function updateQueryParams() {
  const params = new URLSearchParams(window.location.search);
  params.set("view", state.view);
  params.set("filter", state.filter);
  params.set("layout", state.layout);
  window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
}

function setActiveView(view) {
  state.view = view;
  localStorage.setItem("hs_view", view);
  viewButtons.forEach((btn) => btn.classList.toggle("active", btn.dataset.view === view));
  restaurantsContainer.classList.toggle("hidden", view !== "restaurants");
  eventsContainer.classList.toggle("hidden", view !== "events");
  pairedContainer.classList.toggle("hidden", view !== "paired");
  render();
  updateQueryParams();
}

function stripMeta(items) {
  return items.filter((item) => !item._meta);
}

function matchesFilter(text) {
  if (!state.filter) return true;
  return text.toLowerCase().includes(state.filter.toLowerCase());
}

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderRestaurants() {
  const filtered = state.data.restaurants.filter(
    (r) => matchesFilter(r.name) || matchesFilter(r.cuisine) || matchesFilter(r.address || "")
  );
  if (state.layout === "table") {
    const rows = filtered
      .map(
        (r) =>
          `<tr><td>${escapeHTML(r.name)}</td><td>${escapeHTML(r.cuisine)}</td><td>${escapeHTML(
            r.address
          )}</td><td><a href="${escapeHTML(r.url)}" target="_blank" rel="noopener">Link</a></td></tr>`
      )
      .join("");
    restaurantsContainer.innerHTML = `<table><thead><tr><th>Name</th><th>Cuisine</th><th>Address</th><th>Link</th></tr></thead><tbody>${rows}</tbody></table>`;
  } else {
    const cards = filtered
      .map(
        (r) => `<div class="card">
      <h3>${escapeHTML(r.name)}</h3>
      <p>${escapeHTML(r.cuisine)}</p>
      <p class="meta">${escapeHTML(r.address)}</p>
      <a href="${escapeHTML(r.url)}" target="_blank" rel="noopener">View</a>
    </div>`
      )
      .join("");
    restaurantsContainer.innerHTML = `<div class="grid">${cards}</div>`;
  }
}

function renderEvents() {
  const filtered = state.data.events.filter(
    (e) => matchesFilter(e.title) || matchesFilter(e.category) || matchesFilter(e.location || "")
  );
  const cards = filtered
    .map(
      (e) => `<div class="card">
        <h3>${escapeHTML(e.title)}</h3>
        <p>${escapeHTML(e.category)}</p>
        <p class="meta">${escapeHTML(new Date(e.date).toLocaleString())} – ${escapeHTML(e.location)}</p>
        <a href="${escapeHTML(e.url)}" target="_blank" rel="noopener">Details</a>
      </div>`
    )
    .join("");
  eventsContainer.innerHTML = `<div class="grid">${cards}</div>`;
}

function renderPaired() {
  const filtered = state.data.pairings.filter(
    (p) => matchesFilter(p.event) || matchesFilter(p.restaurant) || matchesFilter(p.match_reason || "")
  );
  const cards = filtered
    .map(
      (p) => `<div class="card">
        <h3>${escapeHTML(p.event)}</h3>
        <p>+ ${escapeHTML(p.restaurant)}</p>
        <p class="meta">${escapeHTML(p.match_reason || "Great together")}</p>
        <p><a href="${escapeHTML(p.event_url)}" target="_blank" rel="noopener">Event</a> · <a href="${escapeHTML(
            p.restaurant_url
          )}" target="_blank" rel="noopener">Restaurant</a></p>
      </div>`
    )
    .join("");
  pairedContainer.innerHTML = `<div class="grid">${cards}</div>`;
}

function renderMeta() {
  const items = [];
  if (state.data.meta.generated_at) {
    items.push(`Updated ${new Date(state.data.meta.generated_at).toLocaleString()}`);
  }
  if (state.data.meta.region) {
    items.push(`Region: ${state.data.meta.region}`);
  }
  metaInfo.textContent = items.join(" · ");
}

function applyBranding() {
  const { branding } = state.data;
  if (!branding) return;
  const titleEl = document.getElementById("brand-title");
  const taglineEl = document.getElementById("brand-tagline");
  if (branding.title) titleEl.textContent = branding.title;
  if (branding.tagline) taglineEl.textContent = branding.tagline;
  if (branding.accent_color) {
    document.documentElement.style.setProperty("--hs-accent", branding.accent_color);
  }
}

function render() {
  renderMeta();
  if (state.view === "restaurants") {
    renderRestaurants();
  } else if (state.view === "events") {
    renderEvents();
  } else {
    renderPaired();
  }
}

async function loadData() {
  const [eventsResp, restaurantsResp, configResp, metaResp] = await Promise.all([
    fetch("events.json"),
    fetch("restaurants.json"),
    fetch("config.json"),
    fetch("meta.json"),
  ]);
  const events = await eventsResp.json();
  const restaurants = await restaurantsResp.json();
  const config = await configResp.json();
  const meta = await metaResp.json();
  state.data.events = stripMeta(events);
  state.data.restaurants = stripMeta(restaurants);
  state.data.pairings = meta.pairings || [];
  state.data.meta = meta;
  state.data.branding = config.branding || meta.branding || {};
  applyBranding();
  render();
  document.body.setAttribute("data-hs-ready", "1");
}

viewButtons.forEach((btn) =>
  btn.addEventListener("click", () => {
    setActiveView(btn.dataset.view);
  })
);

filterInput.addEventListener("input", (e) => {
  state.filter = e.target.value;
  render();
  updateQueryParams();
});

layoutSelect.addEventListener("change", (e) => {
  state.layout = e.target.value;
  render();
  updateQueryParams();
});

setActiveView(state.view);
loadData().catch((err) => {
  console.error("Failed to load data", err);
  const message = err && err.message ? err.message : "network or parsing error";
  metaInfo.textContent = `Unable to load data (${message}). Please refresh or try again later.`;
  document.body.setAttribute("data-hs-ready", "error");
});
