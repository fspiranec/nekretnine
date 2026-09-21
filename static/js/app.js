"use strict";

class PropertyExplorer {
  constructor() {
    this.map = L.map("map", { zoomControl: true }).setView([45.25, 16.35], 7);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(this.map);
    this.markers = L.layerGroup().addTo(this.map);
    this.boundaries = L.layerGroup().addTo(this.map);
    this.drawnItems = new L.FeatureGroup().addTo(this.map);
    this.polygon = null;
    this.properties = [];
    this.form = document.querySelector("#filters");
    this.installDrawing();
    this.bindEvents();
    this.loadBoundaries();
    this.loadProperties();
  }

  installDrawing() {
    this.map.addControl(new L.Control.Draw({
      position: "topright", draw: { polygon: { shapeOptions: { color: "#19734b" } }, rectangle: false, circle: false, circlemarker: false, marker: false, polyline: false },
      edit: { featureGroup: this.drawnItems, edit: false, remove: true }
    }));
    this.map.on(L.Draw.Event.CREATED, (event) => {
      this.drawnItems.clearLayers(); this.polygon = event.layer; this.drawnItems.addLayer(event.layer); this.render();
    });
    this.map.on(L.Draw.Event.DELETED, () => { this.polygon = null; this.render(); });
  }

  bindEvents() {
    this.form.addEventListener("submit", (event) => { event.preventDefault(); this.loadProperties(); });
    this.form.addEventListener("reset", () => setTimeout(() => this.loadProperties(), 0));
    document.querySelector("#refreshButton").addEventListener("click", () => this.refresh());
    document.querySelector("#showResultsButton").addEventListener("click", () => this.scrollToResults());
    document.querySelector("#backToMapButton").addEventListener("click", () => {
      document.querySelector("#map").scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  async loadBoundaries() {
    const response = await fetch("/static/data/croatia-counties.geojson");
    if (!response.ok) return;
    const geojson = await response.json();
    const countySelect = document.querySelector("#county");
    const known = new Set([...countySelect.options].map(option => option.value));
    [...new Set(geojson.features.map(feature => feature.properties.name))].sort().forEach(name => {
      if (!known.has(name)) countySelect.add(new Option(name, name));
    });
    L.geoJSON(geojson, { style: { color: "#19734b", weight: 1, opacity: .34, fillOpacity: .025 }, interactive: false }).addTo(this.boundaries);
    const municipalities = await fetch("/static/data/croatia-municipalities.geojson").then(r => r.ok ? r.json() : null);
    if (municipalities) {
      const select = document.querySelector("#municipality"); const existing = new Set([...select.options].map(o => o.value));
      municipalities.features.map(f => f.properties.name).sort().forEach(name => { if (!existing.has(name)) select.add(new Option(name, name)); });
    }
  }

  async loadProperties() {
    const params = new URLSearchParams(new FormData(this.form));
    try {
      const response = await fetch(`/api/properties?${params}`);
      if (!response.ok) throw new Error("Dohvat oglasa nije uspio");
      this.properties = (await response.json()).properties; this.render();
    } catch (error) { document.querySelector("#syncMessage").textContent = error.message; }
  }

  insideSelection(property) {
    if (!this.polygon || property.latitude == null || property.longitude == null) return !this.polygon;
    const point = L.latLng(property.latitude, property.longitude);
    const coordinates = this.polygon.getLatLngs()[0];
    let inside = false;
    for (let i = 0, j = coordinates.length - 1; i < coordinates.length; j = i++) {
      const xi = coordinates[i].lng, yi = coordinates[i].lat, xj = coordinates[j].lng, yj = coordinates[j].lat;
      if (((yi > point.lat) !== (yj > point.lat)) && (point.lng < (xj - xi) * (point.lat - yi) / (yj - yi) + xi)) inside = !inside;
    }
    return inside;
  }

  render() {
    const located = this.properties.filter(property => property.latitude != null && property.longitude != null);
    const missingLocation = this.polygon
      ? this.properties.filter(property => property.latitude == null || property.longitude == null)
      : [];
    const insideArea = located.filter(property => this.insideSelection(property));
    // A polygon cannot classify listings without coordinates. Keep their cards
    // accessible, but report them separately instead of pretending they matched.
    const visible = this.polygon ? [...insideArea, ...missingLocation] : this.properties;
    this.markers.clearLayers();
    insideArea.forEach(property => {
      const popup = `<strong>${this.escape(property.title)}</strong><br><span class="marker-price">${this.money(property.price)}</span><br><a href="${this.escape(property.url)}" target="_blank" rel="noopener noreferrer">Otvori izvorni oglas ↗</a>`;
      L.marker([property.latitude, property.longitude]).bindPopup(popup).addTo(this.markers);
    });
    const grid = document.querySelector("#propertyGrid"); grid.replaceChildren(...visible.map(p => this.card(p)));
    document.querySelector("#resultCount").textContent = visible.length.toLocaleString("hr-HR");
    document.querySelector("#mapResultCount").textContent = visible.length.toLocaleString("hr-HR");
    document.querySelector("#missingLocationCount").textContent = missingLocation.length.toLocaleString("hr-HR");
    document.querySelector("#missingLocationNotice").classList.toggle("d-none", missingLocation.length === 0);
    document.querySelector("#emptyState").classList.toggle("d-none", visible.length !== 0);
  }

  scrollToResults() {
    const section = document.querySelector("#resultsSection");
    section.scrollIntoView({ behavior: "smooth", block: "start" });
    section.focus({ preventScroll: true });
  }

  card(property) {
    const column = document.createElement("div"); column.className = "col";
    const image = property.images[0] || "";
    column.innerHTML = `<article class="card property-card"><div class="property-image-wrap">${image ? `<img class="property-image" loading="lazy" alt="" src="${this.escape(image)}">` : '<div class="property-image"></div>'}</div><div class="card-body d-flex flex-column"><div class="small text-secondary mb-2">${this.escape([property.city, property.municipality].filter(Boolean).join(" · ") || property.county || "Hrvatska")}</div><h3 class="h6 card-title">${this.escape(property.title)}</h3><div class="price mb-2">${this.money(property.price)}</div><div class="facts mb-3"><span>⌂ ${this.area(property.living_area)} stambeno</span><span>◇ ${this.area(property.land_area)} zemljište</span></div><a class="btn btn-outline-dark btn-sm mt-auto" href="${this.escape(property.url)}" target="_blank" rel="noopener noreferrer">Otvori izvorni oglas ↗</a></div></article>`;
    return column;
  }

  async refresh() {
    const button = document.querySelector("#refreshButton"); button.disabled = true;
    const response = await fetch("/api/refresh/opereta", { method: "POST" });
    const data = await response.json(); document.querySelector("#syncMessage").textContent = data.message;
    const timer = setInterval(async () => {
      const status = await fetch("/api/refresh/status").then(r => r.json());
      document.querySelector("#syncMessage").textContent = status.message;
      if (!status.running) { clearInterval(timer); button.disabled = false; this.loadProperties(); }
    }, 1500);
  }

  money(value) { return value == null ? "Cijena na upit" : new Intl.NumberFormat("hr-HR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(value); }
  area(value) { return value == null ? "—" : `${new Intl.NumberFormat("hr-HR").format(value)} m²`; }
  escape(value) { const node = document.createElement("div"); node.textContent = String(value ?? ""); return node.innerHTML; }
}

document.addEventListener("DOMContentLoaded", () => new PropertyExplorer());
