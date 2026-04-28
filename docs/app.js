const CSV_PATH = "data/all_stores_missing_available.csv";
const NEW_CARDS_PATH = "data/new_missing_cards.json";
const RELEASES_PATH = "data/pahe_latest.json";
const COMING_SOON_PATH = "data/coming_soon.json";
const SPECIALS_PATH = "data/specials.json";

const state = {
  rows: [],
  newCardKeys: new Set(),
  search: "",
  store: "",
  rarity: "",
  minPrice: 0,
  maxPrice: 200,
  specialsPayload: null,
  specialsMapRange: "today",
};

const elements = {
  body: document.querySelector("#cards-body"),
  search: document.querySelector("#search"),
  storeFilter: document.querySelector("#store-filter"),
  rarityFilter: document.querySelector("#rarity-filter"),
  minPrice: document.querySelector("#min-price"),
  maxPrice: document.querySelector("#max-price"),
  releaseGrid: document.querySelector("#release-grid"),
  comingSoonGrid: document.querySelector("#coming-soon-grid"),
  specialsList: document.querySelector("#specials-list"),
  specialsMap: document.querySelector("#specials-map"),
  specialsMapRange: document.querySelector("#specials-map-range"),
};

let specialsMap;
let specialsMarkerLayer;

function parseCsv(text) {
  const rows = [];
  let row = [];
  let value = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (quoted && char === '"' && next === '"') {
      value += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (!quoted && char === ",") {
      row.push(value);
      value = "";
    } else if (!quoted && (char === "\n" || char === "\r")) {
      if (char === "\r" && next === "\n") {
        index += 1;
      }
      row.push(value);
      if (row.some((cell) => cell !== "")) {
        rows.push(row);
      }
      row = [];
      value = "";
    } else {
      value += char;
    }
  }

  if (value || row.length) {
    row.push(value);
    rows.push(row);
  }

  const headers = rows.shift() || [];
  return rows.map((cells) =>
    Object.fromEntries(headers.map((header, index) => [header, cells[index] || ""])),
  );
}

function money(value) {
  const amount = Number.parseFloat(value || "0");
  return `R ${amount.toFixed(2)}`;
}

function ordinal(value) {
  const remainder = value % 100;
  if (remainder >= 11 && remainder <= 13) {
    return `${value}th`;
  }
  if (value % 10 === 1) {
    return `${value}st`;
  }
  if (value % 10 === 2) {
    return `${value}nd`;
  }
  if (value % 10 === 3) {
    return `${value}rd`;
  }
  return `${value}th`;
}

function displayDate(value) {
  if (!value) {
    return "";
  }
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) {
    return value;
  }
  const date = new Date(Date.UTC(year, month - 1, day));
  const monthName = new Intl.DateTimeFormat("en-ZA", {
    month: "long",
    timeZone: "UTC",
  }).format(date);
  return `${ordinal(day)} ${monthName} ${year}`;
}

function rowKey(row) {
  return [row.card_number, row.store, row.url].map((value) => (value || "").trim()).join("|");
}

function unique(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function optionList(select, values, label) {
  select.innerHTML = `<option value="">${label}</option>`;
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
}

function filteredRows() {
  const term = state.search.trim().toLowerCase();
  return state.rows.filter((row) => {
    const price = Number.parseFloat(row.price || "0");
    const matchesStore = !state.store || row.store === state.store;
    const matchesRarity = !state.rarity || row.rarity === state.rarity;
    const matchesMinPrice = !Number.isFinite(state.minPrice) || price >= state.minPrice;
    const matchesMaxPrice = !Number.isFinite(state.maxPrice) || price <= state.maxPrice;
    const haystack = [
      row.card_number,
      row.title,
      row.rarity,
      row.store,
      row.set_name,
      row.stock,
    ]
      .join(" ")
      .toLowerCase();
    const matchesSearch = !term || haystack.includes(term);
    return matchesStore && matchesRarity && matchesMinPrice && matchesMaxPrice && matchesSearch;
  });
}

function renderTable(rows) {
  if (!rows.length) {
    elements.body.innerHTML = '<tr><td colspan="7" class="empty">No cards match the filters.</td></tr>';
    return;
  }

  elements.body.innerHTML = "";
  for (const row of rows) {
    const tr = document.createElement("tr");
    const isNew = state.newCardKeys.has(rowKey(row));
    if (isNew) {
      tr.classList.add("new-card-row");
    }
    tr.innerHTML = `
      <td class="card-number"></td>
      <td class="price"></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
    `;

    const cells = tr.querySelectorAll("td");
    cells[0].textContent = row.card_number;
    cells[1].textContent = money(row.price);
    cells[2].textContent = row.title;
    cells[3].textContent = row.rarity || "-";
    cells[4].textContent = row.store;
    cells[5].textContent = row.stock || "-";

    if (isNew) {
      const badge = document.createElement("span");
      badge.className = "new-badge";
      badge.textContent = "New";
      cells[2].prepend(badge);
    }

    const link = document.createElement("a");
    link.className = "buy-link";
    link.href = row.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = "Open";
    cells[6].append(link);

    elements.body.append(tr);
  }
}

function renderPosters(container, items, emptyText) {
  if (!items.length) {
    container.innerHTML = `<p class="empty">${emptyText}</p>`;
    return;
  }

  container.innerHTML = "";
  for (const item of items) {
    const link = document.createElement("a");
    link.className = "poster-card";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.title = item.title;

    const image = document.createElement("img");
    image.src = item.image;
    image.alt = item.title;
    image.loading = "lazy";

    const title = document.createElement("span");
    const releaseDate = displayDate(item.release_date);
    title.textContent = releaseDate ? `${item.title} (${releaseDate})` : item.title;

    link.append(image, title);
    container.append(link);
  }
}

function renderSpecials(payload) {
  state.specialsPayload = payload;
  const groups = payload.groups || payload.items || [];
  const locations = payload.locations || {};
  if (payload.error) {
    elements.specialsList.innerHTML = `<p class="empty">${payload.error}</p>`;
    return;
  }
  if (!groups.length) {
    elements.specialsList.innerHTML = '<p class="empty">No specials found.</p>';
    return;
  }

  elements.specialsList.innerHTML = "";
  const dayOrder = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
  ];
  const today = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    timeZone: "Africa/Johannesburg",
  }).format(new Date());
  const todayIndex = dayOrder.indexOf(today);
  const rollingWeek = [...dayOrder.slice(todayIndex), ...dayOrder.slice(0, todayIndex)];
  renderSpecialsMapForRange(groups, locations, rollingWeek);

  for (const day of rollingWeek) {
    const dayItems = [];
    for (const group of groups) {
      if ((group.days || []).includes(day)) {
        dayItems.push(...(group.items || []));
      }
    }

    elements.specialsList.append(specialDayElement(day, dayItems, day === today));
  }
}

function selectedMapDays(rollingWeek) {
  if (state.specialsMapRange === "today") {
    return rollingWeek.slice(0, 1);
  }
  if (state.specialsMapRange === "next-7") {
    return rollingWeek;
  }
  return rollingWeek;
}

function renderSpecialsMapForRange(groups, locations, rollingWeek) {
  const days = selectedMapDays(rollingWeek);
  const items = [];
  for (const group of groups) {
    const matchingDays = (group.days || []).filter((day) => days.includes(day));
    for (const item of group.items || []) {
      for (const day of matchingDays) {
        items.push({ ...item, mapDay: day });
      }
    }
  }
  renderSpecialsMap(items, locations);
}

function normalizeVenue(value) {
  return (value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function locationForVenue(venue, locations) {
  const normalizedVenue = normalizeVenue(venue);
  for (const location of Object.values(locations)) {
    const normalizedLocation = normalizeVenue(location.venue);
    if (
      normalizedVenue === normalizedLocation ||
      normalizedVenue.startsWith(normalizedLocation) ||
      normalizedLocation.startsWith(normalizedVenue)
    ) {
      return location;
    }
  }
  return null;
}

function renderSpecialsMap(items, locations) {
  if (!window.L) {
    elements.specialsMap.innerHTML = '<p class="empty">Map could not load.</p>';
    return;
  }

  const venueGroups = groupItemsByVenue(items)
    .map((group) => ({
      ...group,
      location: locationForVenue(group.venue, locations),
    }))
    .filter((group) => group.location);

  if (!venueGroups.length) {
    elements.specialsMap.innerHTML = '<p class="empty">No mapped specials for today.</p>';
    return;
  }

  if (!specialsMap) {
    specialsMap = L.map(elements.specialsMap, {
      scrollWheelZoom: true,
    }).setView([-33.9249, 18.4241], 12);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
    }).addTo(specialsMap);
    specialsMarkerLayer = L.layerGroup().addTo(specialsMap);
  }

  specialsMarkerLayer.clearLayers();
  const bounds = [];
  for (const group of venueGroups) {
    const location = group.location;
    const deals = group.items
      .map((item) => `<li>${item.mapDay}: ${item.deal || item.description || item.title}</li>`)
      .join("");
    const title = location.url
      ? `<a href="${location.url}" target="_blank" rel="noreferrer">${group.venue}</a>`
      : group.venue;
    const marker = L.marker([location.lat, location.lng]).bindPopup(
      `<strong>${title}</strong><ul>${deals}</ul>`,
    );
    marker.addTo(specialsMarkerLayer);
    bounds.push([location.lat, location.lng]);
  }

  if (bounds.length === 1) {
    specialsMap.setView(bounds[0], 14);
  } else {
    specialsMap.fitBounds(bounds, { padding: [24, 24] });
  }
  setTimeout(() => specialsMap.invalidateSize(), 0);
}

function specialDayElement(day, items, isToday) {
    const section = document.createElement("section");
    section.className = "special-group";
    if (isToday) {
      section.classList.add("today-special-group");
    }

    const heading = document.createElement("h4");
    heading.textContent = isToday ? `Today (${day})` : day;
    section.append(heading);

    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "special-empty";
      empty.textContent = "No specials listed.";
      section.append(empty);
      return section;
    }

    const list = document.createElement("ul");
    for (const venueGroup of groupItemsByVenue(items)) {
      const listItem = document.createElement("li");
      const venue = document.createElement("strong");
      venue.textContent = venueGroup.venue;
      listItem.append(venue);

      if (venueGroup.items.length === 1 && venueGroup.items[0].url) {
        listItem.textContent = "";
        const link = document.createElement("a");
        link.href = venueGroup.items[0].url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = `${venueGroup.venue} - ${venueGroup.items[0].deal || venueGroup.items[0].description || ""}`;
        listItem.append(link);
      } else if (venueGroup.items.length === 1) {
        const deal = document.createElement("span");
        deal.textContent = ` - ${venueGroup.items[0].deal || venueGroup.items[0].description || ""}`;
        listItem.append(deal);
      } else {
        const nested = document.createElement("ul");
        nested.className = "special-deal-list";
        for (const item of venueGroup.items) {
          const nestedItem = document.createElement("li");
          if (item.url) {
            const link = document.createElement("a");
            link.href = item.url;
            link.target = "_blank";
            link.rel = "noreferrer";
            link.textContent = item.deal || item.description || item.title;
            nestedItem.append(link);
          } else {
            nestedItem.textContent = item.deal || item.description || item.title;
          }
          nested.append(nestedItem);
        }
        listItem.append(nested);
      }
      list.append(listItem);
    }

    section.append(list);
    return section;
}

function groupItemsByVenue(items) {
  const groups = [];
  const byVenue = new Map();
  for (const item of items) {
    const venue = item.venue || item.title || "Special";
    if (!byVenue.has(venue)) {
      const group = { venue, items: [] };
      byVenue.set(venue, group);
      groups.push(group);
    }
    byVenue.get(venue).items.push(item);
  }
  return groups;
}

function render() {
  const rows = filteredRows().sort((left, right) => {
    const price = Number.parseFloat(left.price || "0") - Number.parseFloat(right.price || "0");
    if (price !== 0) {
      return price;
    }
    return `${left.card_number} ${left.store} ${left.title}`.localeCompare(
      `${right.card_number} ${right.store} ${right.title}`,
    );
  });

  renderTable(rows);
}

async function loadReleases() {
  try {
    const response = await fetch(RELEASES_PATH, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Could not load ${RELEASES_PATH}`);
    }
    const payload = await response.json();
    renderPosters(elements.releaseGrid, payload.items || [], "No releases found.");
  } catch (error) {
    elements.releaseGrid.innerHTML = `<p class="empty">${error.message}</p>`;
  }
}

async function loadComingSoon() {
  try {
    const response = await fetch(COMING_SOON_PATH, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Could not load ${COMING_SOON_PATH}`);
    }
    const payload = await response.json();
    renderPosters(elements.comingSoonGrid, payload.items || [], "No coming soon movies found.");
  } catch (error) {
    elements.comingSoonGrid.innerHTML = `<p class="empty">${error.message}</p>`;
  }
}

async function loadSpecials() {
  try {
    const response = await fetch(SPECIALS_PATH, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Could not load ${SPECIALS_PATH}`);
    }
    renderSpecials(await response.json());
  } catch (error) {
    elements.specialsList.innerHTML = `<p class="empty">${error.message}</p>`;
  }
}

async function load() {
  try {
    const response = await fetch(CSV_PATH, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Could not load ${CSV_PATH}`);
    }
    state.rows = parseCsv(await response.text());
    try {
      const newCardsResponse = await fetch(NEW_CARDS_PATH, { cache: "no-store" });
      if (newCardsResponse.ok) {
        const payload = await newCardsResponse.json();
        state.newCardKeys = new Set(payload.keys || []);
      }
    } catch {
      state.newCardKeys = new Set();
    }
    optionList(elements.storeFilter, unique(state.rows.map((row) => row.store)), "All stores");
    optionList(elements.rarityFilter, unique(state.rows.map((row) => row.rarity)), "All rarities");
    render();
  } catch (error) {
    elements.body.innerHTML = `<tr><td colspan="7" class="empty">${error.message}</td></tr>`;
  }
}

elements.search.addEventListener("input", (event) => {
  state.search = event.target.value;
  render();
});

elements.storeFilter.addEventListener("change", (event) => {
  state.store = event.target.value;
  render();
});

elements.rarityFilter.addEventListener("change", (event) => {
  state.rarity = event.target.value;
  render();
});

elements.minPrice.addEventListener("input", (event) => {
  state.minPrice = event.target.value === "" ? Number.NEGATIVE_INFINITY : Number(event.target.value);
  render();
});

elements.maxPrice.addEventListener("input", (event) => {
  state.maxPrice = event.target.value === "" ? Number.POSITIVE_INFINITY : Number(event.target.value);
  render();
});

elements.specialsMapRange.addEventListener("change", (event) => {
  state.specialsMapRange = event.target.value;
  if (state.specialsPayload) {
    renderSpecials(state.specialsPayload);
  }
});

load();
loadReleases();
loadComingSoon();
loadSpecials();
