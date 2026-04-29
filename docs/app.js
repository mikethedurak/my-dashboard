const CSV_PATH = "data/all_stores_missing_available.csv";
const NEW_CARDS_PATH = "data/new_missing_cards.json";
const RELEASES_PATH = "data/pahe_latest.json";
const COMING_SOON_PATH = "data/coming_soon.json";
const SPECIALS_PATH = "data/specials.json";
const QUICKET_EVENTS_PATH = "data/quicket_events.json";
const WEATHER_PATH =
  "https://api.open-meteo.com/v1/forecast?latitude=-33.9249&longitude=18.4241&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=Africa%2FJohannesburg&forecast_days=7";
const HOLIDAYS_PATH = "https://date.nager.at/api/v3/publicholidays/{year}/ZA";
const METADATA_PATH = "data/metadata.json";
const GOOGLE_CALENDAR_EVENTS_PATH = "data/google_calendar_events.json";
const WEEK_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const state = {
  rows: [],
  newCardKeys: new Set(),
  search: "",
  store: "",
  rarity: "",
  minPrice: 0,
  maxPrice: 200,
  specialsPayload: null,
  quicketEvents: [],
  specialsMapRange: "next-7",
  mapSources: {
    places: true,
    specials: true,
    events: true,
  },
  selectedMapTypes: new Set(),
  availableMapTypes: [],
  selectedMapCategories: new Set(),
  availableMapCategories: [],
  weatherPayload: null,
  customStartDate: "",
  customEndDate: "",
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
  weatherCards: document.querySelector("#weather-cards"),
  specialsList: document.querySelector("#specials-list"),
  specialsMap: document.querySelector("#specials-map"),
  customStartDate: document.querySelector("#custom-start-date"),
  customEndDate: document.querySelector("#custom-end-date"),
  customStartDateButton: document.querySelector("#custom-start-date-button"),
  customEndDateButton: document.querySelector("#custom-end-date-button"),
  mapSourcePlaces: document.querySelector("#map-source-places"),
  mapSourceSpecials: document.querySelector("#map-source-specials"),
  mapSourceEvents: document.querySelector("#map-source-events"),
  locateMe: document.querySelector("#locate-me"),
  mapTypeFilters: document.querySelector("#map-type-filters"),
  mapCategoryFilters: document.querySelector("#map-category-filters"),
  mapDetailPanel: document.querySelector("#map-detail-panel"),
  quicketEventsList: document.querySelector("#quicket-events-list"),
  todayDate: document.querySelector("#today-date"),
  lastScraped: document.querySelector("#last-scraped"),
  themeToggle: document.querySelector("#theme-toggle"),
};
const mapRangeButtons = [...document.querySelectorAll(".map-range-button[data-range]")];

let specialsMap;
let specialsMarkerLayer;
let myLocationMarker;
let myLocationLatLng = null;
let hasAutoFitMap = true;
let forceNextMapFit = false;
let selectedMapItemKey = "";
let currentMapItems = [];
let mapMarkersByKey = new Map();
const markerIcons = {
  places: L.icon({
    iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
  }),
  specials: L.icon({
    iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
  }),
  events: L.icon({
    iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
  }),
  myLocation: L.icon({
    iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-orange.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
  }),
};

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

function displayDateTime(value) {
  if (!value) {
    return "Date unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-ZA", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Africa/Johannesburg",
  }).format(date);
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

function setHeaderDate() {
  if (!elements.todayDate) {
    return;
  }
  const now = new Date();
  elements.todayDate.textContent = new Intl.DateTimeFormat("en-ZA", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Africa/Johannesburg",
  }).format(now);
}

function setLastScrapedText(value) {
  if (!elements.lastScraped) {
    return;
  }
  if (!value) {
    elements.lastScraped.textContent = "Last scraped: -";
    return;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    elements.lastScraped.textContent = `Last scraped: ${value}`;
    return;
  }
  const formatted = new Intl.DateTimeFormat("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Africa/Johannesburg",
  }).format(parsed);
  elements.lastScraped.textContent = `Last scraped: ${formatted}`;
}

function themeStorageKey() {
  return "my-dashboard:theme:v1";
}

function applyTheme(theme) {
  const finalTheme = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", finalTheme);
  if (elements.themeToggle) {
    elements.themeToggle.textContent = finalTheme === "dark" ? "Day mode" : "Night mode";
  }
}

function loadThemePreference() {
  try {
    return localStorage.getItem(themeStorageKey()) || "";
  } catch {
    return "";
  }
}

function saveThemePreference(theme) {
  try {
    localStorage.setItem(themeStorageKey(), theme);
  } catch {
    // Ignore storage failures.
  }
}

function weatherIcon(weatherCode) {
  if (weatherCode === 0) {
    return "\uD83C\uDF1E";
  }
  if ([1, 2, 3].includes(weatherCode)) {
    return "\uD83C\uDF24\uFE0F";
  }
  if ([45, 48].includes(weatherCode)) {
    return "\uD83C\uDF2B\uFE0F";
  }
  if ([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82].includes(weatherCode)) {
    return "\uD83C\uDF27\uFE0F";
  }
  if ([71, 73, 75, 77, 85, 86].includes(weatherCode)) {
    return "\u2744\uFE0F";
  }
  if ([95, 96, 99].includes(weatherCode)) {
    return "\u26C8\uFE0F";
  }
  return "\u2601\uFE0F";
}

function weatherDayLabel(dateValue) {
  const date = new Date(`${dateValue}T00:00:00`);
  return new Intl.DateTimeFormat("en-ZA", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    timeZone: "Africa/Johannesburg",
  }).format(date);
}

function weekdayFromDate(dateValue) {
  const date = new Date(`${dateValue}T00:00:00`);
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    timeZone: "Africa/Johannesburg",
  }).format(date);
}

function renderWeather(payload) {
  const daily = payload?.daily;
  if (!daily?.time?.length) {
    elements.weatherCards.innerHTML = '<p class="empty">Weather data not available.</p>';
    return;
  }

  const items = daily.time.map((date, index) => ({
    date,
    code: daily.weathercode[index],
    max: daily.temperature_2m_max[index],
    min: daily.temperature_2m_min[index],
  }));

  Promise.all([
    loadHolidaysForDates(items.map((item) => item.date)),
    loadCalendarEventsByDate(items.map((item) => item.date)),
  ])
    .then(([holidayByDate, calendarByDate]) => {
      elements.weatherCards.innerHTML = "";
      for (const item of items) {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "weather-card";
        const weekday = weekdayFromDate(item.date);
        if (WEEK_DAYS.includes(state.specialsMapRange) && state.specialsMapRange === weekday) {
          card.classList.add("is-selected");
        }
        card.addEventListener("click", () => {
          clearCustomDateRange();
          state.specialsMapRange = weekday;
          applyMapRangeChange();
        });
        const holidayName = holidayByDate.get(item.date) || "";
        const holidayHtml = holidayName ? `<p class="weather-holiday">${holidayName}</p>` : "";
        const calendarItems = calendarByDate.get(item.date) || [];
        const calendarHtml = calendarItems
          .slice(0, 2)
          .map((entry) => {
            const cls = entry.type === "birthday" ? "weather-birthday" : "weather-calendar";
            return `<p class="${cls}">${entry.title}</p>`;
          })
          .join("");
        card.innerHTML = `
          <p class="weather-day">${weatherDayLabel(item.date)}</p>
          <p class="weather-icon">${weatherIcon(item.code)}</p>
          <p class="weather-temp">${Math.round(item.max)}° / ${Math.round(item.min)}°</p>
          ${holidayHtml}
          ${calendarHtml}
        `;
        elements.weatherCards.append(card);
      }
    })
    .catch(() => {
      elements.weatherCards.innerHTML = "";
      for (const item of items) {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "weather-card";
        const weekday = weekdayFromDate(item.date);
        if (WEEK_DAYS.includes(state.specialsMapRange) && state.specialsMapRange === weekday) {
          card.classList.add("is-selected");
        }
        card.addEventListener("click", () => {
          clearCustomDateRange();
          state.specialsMapRange = weekday;
          applyMapRangeChange();
        });
        card.innerHTML = `
          <p class="weather-day">${weatherDayLabel(item.date)}</p>
          <p class="weather-icon">${weatherIcon(item.code)}</p>
          <p class="weather-temp">${Math.round(item.max)}° / ${Math.round(item.min)}°</p>
        `;
        elements.weatherCards.append(card);
      }
    });
}

async function loadHolidaysForDates(dateStrings) {
  const years = unique(dateStrings.map((value) => value.split("-")[0]));
  const holidayByDate = new Map();
  for (const year of years) {
    const response = await fetch(HOLIDAYS_PATH.replace("{year}", year), { cache: "no-store" });
    if (!response.ok) {
      continue;
    }
    const payload = await response.json();
    if (!Array.isArray(payload)) {
      continue;
    }
    for (const holiday of payload) {
      if (dateStrings.includes(holiday.date)) {
        holidayByDate.set(holiday.date, holiday.localName || holiday.name || "Public Holiday");
      }
    }
  }
  return holidayByDate;
}

async function loadCalendarEventsByDate(dateStrings) {
  const byDate = new Map();
  try {
    const response = await fetch(GOOGLE_CALENDAR_EVENTS_PATH, { cache: "no-store" });
    if (!response.ok) {
      return byDate;
    }
    const payload = await response.json();
    const items = Array.isArray(payload?.items) ? payload.items : [];
    for (const item of items) {
      const date = item.date || (item.start || "").split("T")[0];
      if (!date || !dateStrings.includes(date) || item.type === "error") {
        continue;
      }
      if (!byDate.has(date)) {
        byDate.set(date, []);
      }
      byDate.get(date).push({
        type: item.type || "calendar",
        title: item.title || "Calendar event",
      });
    }
  } catch {
    return byDate;
  }
  return byDate;
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
  const dayIndex = new Map(dayOrder.map((name, index) => [name, index]));
  const itemDaysByKey = new Map();

  for (const group of groups) {
    const groupDays = (group.days || []).filter((day) => dayIndex.has(day));
    for (const item of group.items || []) {
      const key = specialItemKey(item);
      if (!itemDaysByKey.has(key)) {
        itemDaysByKey.set(key, new Set());
      }
      const bucket = itemDaysByKey.get(key);
      for (const day of groupDays) {
        bucket.add(day);
      }
    }
  }

  renderTagFilters(locations);
  renderMap();

  for (const day of rollingWeek) {
    const dayItems = [];
    for (const group of groups) {
      if ((group.days || []).includes(day)) {
        for (const item of group.items || []) {
          const fullDays = [...(itemDaysByKey.get(specialItemKey(item)) || new Set([day]))];
          dayItems.push({ ...item, allDays: fullDays });
        }
      }
    }

    elements.specialsList.append(specialDayElement(day, dayItems, day === today));
  }
}

function specialItemKey(item) {
  return [
    item.venue || item.title || "",
    item.details || "",
    item.price || "",
    item.time || "",
    item.deal || item.description || "",
  ]
    .join("|")
    .toLowerCase()
    .trim();
}

function formatDaysSummary(days) {
  const dayOrder = WEEK_DAYS;
  const dayIndex = new Map(dayOrder.map((name, index) => [name, index]));
  const sorted = [...new Set((days || []).filter((day) => dayIndex.has(day)))].sort(
    (left, right) => dayIndex.get(left) - dayIndex.get(right),
  );
  if (!sorted.length) {
    return "";
  }

  const ranges = [];
  let start = sorted[0];
  let previous = sorted[0];
  for (let index = 1; index < sorted.length; index += 1) {
    const current = sorted[index];
    if (dayIndex.get(current) === dayIndex.get(previous) + 1) {
      previous = current;
      continue;
    }
    ranges.push([start, previous]);
    start = current;
    previous = current;
  }
  ranges.push([start, previous]);

  const parts = ranges.map(([rangeStart, rangeEnd]) => {
    const span = dayIndex.get(rangeEnd) - dayIndex.get(rangeStart) + 1;
    if (span >= 3) {
      return `${rangeStart} to ${rangeEnd}`;
    }
    if (span === 2) {
      return `${rangeStart}, ${rangeEnd}`;
    }
    return rangeStart;
  });
  return parts.join(", ");
}

function typesFromLocations(locations) {
  const tags = [];
  for (const location of Object.values(locations || {})) {
    for (const tag of location.types || location.tags || []) {
      tags.push(tag);
    }
  }
  return unique(tags);
}

function categoriesFromLocations(locations) {
  const tags = [];
  for (const location of Object.values(locations || {})) {
    for (const tag of location.categories || []) {
      tags.push(tag);
    }
  }
  return unique(tags);
}

function syncSelectedWithAvailable(selectedSet, availableList, autoSelectWhenEmpty = true) {
  if (!selectedSet.size) {
    if (autoSelectWhenEmpty) {
      for (const tag of availableList) {
        selectedSet.add(tag);
      }
    }
    return selectedSet;
  }
  const filtered = new Set([...selectedSet].filter((tag) => availableList.includes(tag)));
  if (!filtered.size && autoSelectWhenEmpty) {
    for (const tag of availableList) {
      filtered.add(tag);
    }
  }
  return filtered;
}

function renderFilterCheckboxes(container, values, selectedSet, emptyText, onToggle) {
  if (!values.length) {
    container.innerHTML = `<p class="empty">${emptyText}</p>`;
    return;
  }

  container.innerHTML = "";
  for (const tag of values) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = tag;
    input.checked = selectedSet.has(tag);
    input.addEventListener("change", () => {
      onToggle(tag, input.checked);
    });
    label.append(input, ` ${tag}`);
    container.append(label);
  }
}

function renderTagFilters(locations) {
  const types = typesFromLocations(locations);
  const categories = categoriesFromLocations(locations);
  state.availableMapTypes = types;
  state.availableMapCategories = categories;
  state.selectedMapTypes = syncSelectedWithAvailable(state.selectedMapTypes, types);
  state.selectedMapCategories = syncSelectedWithAvailable(
    state.selectedMapCategories,
    categories,
    false,
  );

  renderFilterCheckboxes(
    elements.mapTypeFilters,
    types,
    state.selectedMapTypes,
    "No types yet.",
    (tag, checked) => {
      if (checked) {
        state.selectedMapTypes.add(tag);
      } else {
        state.selectedMapTypes.delete(tag);
      }
      renderMap();
    },
  );

  renderFilterCheckboxes(
    elements.mapCategoryFilters,
    categories,
    state.selectedMapCategories,
    "No categories yet.",
    (tag, checked) => {
      if (checked) {
        state.selectedMapCategories.add(tag);
      } else {
        state.selectedMapCategories.delete(tag);
      }
      renderMap();
    },
  );
}

function renderQuicketEvents(events) {
  if (!events.length) {
    elements.quicketEventsList.innerHTML = '<p class="empty">No Quicket events found.</p>';
    return;
  }

  elements.quicketEventsList.innerHTML = "";
  for (const event of events) {
    const card = document.createElement("a");
    card.className = "event-card";
    card.href = event.url;
    card.target = "_blank";
    card.rel = "noreferrer";

    const image = document.createElement("img");
    image.src = event.image || "";
    image.alt = event.title || "Quicket event";
    image.loading = "lazy";

    const details = document.createElement("div");
    details.className = "event-card-body";

    const date = document.createElement("span");
    date.className = "event-date";
    date.textContent = displayDateTime(event.start);

    const title = document.createElement("strong");
    title.textContent = event.title || "Untitled event";

    const venue = document.createElement("span");
    venue.className = "event-venue";
    venue.textContent = [event.venue, event.locality].filter(Boolean).join(", ");

    details.append(date, title, venue);
    if (event.image) {
      card.append(image, details);
    } else {
      card.classList.add("event-card-no-image");
      card.append(details);
    }
    elements.quicketEventsList.append(card);
  }
}

function selectedMapDays(rollingWeek) {
  if (state.customStartDate || state.customEndDate) {
    const nowDate = new Date();
    const defaultStart = `${nowDate.getFullYear()}-${String(nowDate.getMonth() + 1).padStart(2, "0")}-${String(nowDate.getDate()).padStart(2, "0")}`;
    const start = state.customStartDate || defaultStart;
    const end = state.customEndDate || start;
    const weekdays = weekdaysInRange(start, end);
    return weekdays.length ? weekdays : rollingWeek;
  }
  if (state.specialsMapRange === "today") {
    return rollingWeek.slice(0, 1);
  }
  if (state.specialsMapRange === "next-7") {
    return rollingWeek;
  }
  if (WEEK_DAYS.includes(state.specialsMapRange)) {
    return [state.specialsMapRange];
  }
  return rollingWeek;
}

function weekdaysInRange(startDateValue, endDateValue) {
  if (!startDateValue || !endDateValue) {
    return [];
  }
  const start = new Date(`${startDateValue}T00:00:00`);
  const end = new Date(`${endDateValue}T23:59:59`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) {
    return [];
  }
  const days = new Set();
  const cursor = new Date(start);
  while (cursor <= end) {
    const day = new Intl.DateTimeFormat("en-US", {
      weekday: "long",
      timeZone: "Africa/Johannesburg",
    }).format(cursor);
    if (WEEK_DAYS.includes(day)) {
      days.add(day);
    }
    cursor.setDate(cursor.getDate() + 1);
  }
  return WEEK_DAYS.filter((day) => days.has(day));
}

function mapRangeWindow() {
  const now = new Date();
  const start = new Date(now);
  let end;
  if (state.customStartDate || state.customEndDate) {
    const startCustom = state.customStartDate ? new Date(`${state.customStartDate}T00:00:00`) : new Date(now);
    const endCustom = state.customEndDate
      ? new Date(`${state.customEndDate}T23:59:59`)
      : new Date(startCustom.getTime() + 365 * 24 * 60 * 60 * 1000);
    if (!Number.isNaN(startCustom.getTime()) && !Number.isNaN(endCustom.getTime())) {
      if (endCustom < startCustom) {
        return { start: startCustom, end: startCustom };
      }
      return { start: startCustom, end: endCustom };
    }
  }
  if (state.specialsMapRange === "today") {
    end = new Date(now);
    end.setHours(23, 59, 59, 999);
  } else if (state.specialsMapRange === "next-7") {
    end = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
  } else if (state.specialsMapRange === "next-month") {
    end = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
  } else if (WEEK_DAYS.includes(state.specialsMapRange)) {
    const targetIndex = WEEK_DAYS.indexOf(state.specialsMapRange);
    const currentIndex = new Intl.DateTimeFormat("en-US", {
      weekday: "long",
      timeZone: "Africa/Johannesburg",
    }).format(now);
    const currentPos = WEEK_DAYS.indexOf(currentIndex);
    const dayDelta = (targetIndex - currentPos + 7) % 7;
    start.setHours(0, 0, 0, 0);
    start.setDate(start.getDate() + dayDelta);
    end = new Date(start);
    end.setHours(23, 59, 59, 999);
  } else {
    end = new Date(now.getTime() + 365 * 24 * 60 * 60 * 1000);
  }
  return { start, end };
}

function syncRangeButtons() {
  const usingDateRange = Boolean(state.customStartDate || state.customEndDate);
  for (const button of mapRangeButtons) {
    button.classList.toggle("is-selected", !usingDateRange && button.dataset.range === state.specialsMapRange);
  }
  if (elements.customStartDateButton) {
    elements.customStartDateButton.classList.toggle("is-selected", Boolean(state.customStartDate));
    elements.customStartDateButton.textContent = state.customStartDate || "Start date";
  }
  if (elements.customEndDateButton) {
    elements.customEndDateButton.classList.toggle("is-selected", Boolean(state.customEndDate));
    elements.customEndDateButton.textContent = state.customEndDate || "End date";
  }
}

function applyMapRangeChange() {
  renderMap();
  if (state.weatherPayload) {
    renderWeather(state.weatherPayload);
  }
  syncRangeButtons();
}

function clearCustomDateRange() {
  state.customStartDate = "";
  state.customEndDate = "";
  if (elements.customStartDate) {
    elements.customStartDate.value = "";
  }
  if (elements.customEndDate) {
    elements.customEndDate.value = "";
  }
}

function specialsItemsForRange(groups, rollingWeek) {
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
  return items;
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

function mapItemFromSpecialGroup(group) {
  const location = group.location;
  const bySpecial = new Map();
  for (const item of group.items || []) {
    const key = specialItemKey(item);
    if (!bySpecial.has(key)) {
      bySpecial.set(key, {
        details: item.details || item.deal || item.description || "",
        price: item.price || "",
        time: item.time || "",
        days: new Set(),
      });
    }
    const entry = bySpecial.get(key);
    if (item.mapDay) {
      entry.days.add(item.mapDay);
    }
  }
  const specialEntries = [...bySpecial.values()].map((entry) => ({
    details: entry.details,
    price: entry.price,
    time: entry.time,
    daysText: formatDaysSummary([...entry.days]) || [...entry.days].join(", "),
  }));
  return {
    source: "specials",
    lat: location.lat,
    lng: location.lng,
    title: group.venue,
    url: location.url,
    tags: location.tags || [],
    specialEntries,
    details: group.items.map((item) => `${item.mapDay}: ${item.deal || item.description || item.title}`),
  };
}

function mapItemFromPlace(location) {
  return {
    source: "places",
    lat: location.lat,
    lng: location.lng,
    title: location.venue,
    url: location.url,
    types: location.types || location.tags || [],
    categories: location.categories || [],
    details: [
      "Place",
      (location.types || location.tags || []).length ? `Type: ${(location.types || location.tags || []).join(", ")}` : "No type",
      (location.categories || []).length ? `Category: ${(location.categories || []).join(", ")}` : "No category",
    ],
  };
}

function mapItemFromEvent(event) {
  if (!Number.isFinite(event.lat) || !Number.isFinite(event.lng)) {
    return null;
  }
  const startAt = event.start ? new Date(event.start) : null;
  if (!startAt || Number.isNaN(startAt.getTime())) {
    return null;
  }
  const window = mapRangeWindow();
  if (startAt < window.start || startAt > window.end) {
    return null;
  }
  return {
    source: "events",
    id: `event:${event.url || `${event.title}|${event.start}`}`,
    lat: event.lat,
    lng: event.lng,
    title: event.title,
    url: event.url,
    types: [],
    categories: [],
    details: [displayDateTime(event.start), [event.venue, event.locality].filter(Boolean).join(", ")],
    event,
  };
}

function mapItemKey(item) {
  if (!item) {
    return "";
  }
  if (item.id) {
    return item.id;
  }
  return `${item.source}:${item.title}:${item.lat}:${item.lng}`;
}

function venueKey(value) {
  return normalizeVenue(value || "");
}

function focusSpecialOnMap(venueName) {
  if (!specialsMap || !venueName) {
    return;
  }
  const key = venueKey(venueName);
  const selectedItem =
    currentMapItems.find((item) => item.source === "specials" && venueKey(item.title) === key) ||
    currentMapItems.find((item) => item.source === "places" && venueKey(item.title) === key) ||
    null;
  const marker = mapMarkersByKey.get(`specials:${key}`) || mapMarkersByKey.get(`places:${key}`);
  if (marker) {
    const latLng = marker.getLatLng();
    specialsMap.setView(latLng, 14, { animate: true });
    if (selectedItem) {
      selectedMapItemKey = mapItemKey(selectedItem);
      renderMapDetail(selectedItem);
    }
    return;
  }
  const locations = state.specialsPayload?.locations || {};
  const location = locationForVenue(venueName, locations);
  if (location) {
    specialsMap.setView([location.lat, location.lng], 14, { animate: true });
    if (selectedItem) {
      selectedMapItemKey = mapItemKey(selectedItem);
      renderMapDetail(selectedItem);
    }
  }
}

function eventListCard(event) {
  const when = displayDateTime(event.start);
  const where = [event.venue, event.locality].filter(Boolean).join(", ");
  const imageHtml = event.image ? `<img src="${event.image}" alt="${event.title || "Event"}">` : "";
  return `
    <article class="map-event-list-card">
      ${imageHtml}
      <div class="map-event-list-body">
        <h5>${event.title || "Untitled event"}</h5>
        <p><strong>When:</strong> ${when}</p>
        <p><strong>Where:</strong> ${where || "-"}</p>
        <p><a href="${event.url}" target="_blank" rel="noreferrer">Open event</a></p>
      </div>
    </article>
  `;
}

function renderMapEventList() {
  if (!specialsMap) {
    elements.mapDetailPanel.innerHTML = '<p class="empty">Map is loading...</p>';
    return;
  }
  const bounds = specialsMap.getBounds();
  const visibleEvents = currentMapItems.filter((item) =>
    item.source === "events" && bounds.contains([item.lat, item.lng]),
  );
  if (!visibleEvents.length) {
    elements.mapDetailPanel.innerHTML = '<p class="empty">No events in this map view.</p>';
    return;
  }
  const list = visibleEvents.map((item) => eventListCard(item.event)).join("");
  elements.mapDetailPanel.innerHTML = `
    <div class="map-event-list-header">
      <p class="map-detail-source">Events In View</p>
      <p>${visibleEvents.length} visible</p>
    </div>
    <div class="map-event-list">${list}</div>
  `;
}

function renderMapDetail(item) {
  if (!item) {
    selectedMapItemKey = "";
    renderMapEventList();
    return;
  }

  if (item.source === "events" && item.event) {
    const event = item.event;
    const when = displayDateTime(event.start);
    const where = [event.venue, event.locality].filter(Boolean).join(", ");
    const address = event.address || "";
    const imageHtml = event.image
      ? `<img src="${event.image}" alt="${event.title || "Event"}">`
      : "";
    elements.mapDetailPanel.innerHTML = `
      <article class="map-detail-card">
        ${imageHtml}
        <div class="map-detail-body">
          <button type="button" class="map-back-button" id="map-back-button">Back to event list</button>
          <p class="map-detail-source">Event</p>
          <h4>${event.title || "Untitled event"}</h4>
          <p><strong>When:</strong> ${when}</p>
          <p><strong>Where:</strong> ${where || "-"}</p>
          <p><strong>Address:</strong> ${address || "-"}</p>
          <p><a href="${event.url}" target="_blank" rel="noreferrer">Open event</a></p>
        </div>
      </article>
    `;
    const backButton = document.querySelector("#map-back-button");
    if (backButton) {
      backButton.addEventListener("click", () => renderMapDetail(null));
    }
    return;
  }

  const title = item.url
    ? `<a href="${item.url}" target="_blank" rel="noreferrer">${item.title}</a>`
    : item.title;
  if (item.source === "specials") {
    const entries = (item.specialEntries || [])
      .map(
        (entry) => {
          const lines = [entry.details, entry.price, entry.time, entry.daysText]
            .filter((value) => (value || "").trim())
            .map((value) => `<p>${value}</p>`)
            .join("");
          return `<div class="map-special-entry">${lines}</div>`;
        },
      )
      .join("");
    elements.mapDetailPanel.innerHTML = `
      <article class="map-detail-card">
        <div class="map-detail-body">
          <button type="button" class="map-back-button" id="map-back-button">Back to event list</button>
          <p class="map-detail-source">Special</p>
          <h4>${title}</h4>
          ${entries || ""}
        </div>
      </article>
    `;
    const backButton = document.querySelector("#map-back-button");
    if (backButton) {
      backButton.addEventListener("click", () => renderMapDetail(null));
    }
    return;
  }
  const details = (item.details || []).map((detail) => `<li>${detail}</li>`).join("");
  const sourceLabel = item.source === "places" ? "Place" : "Special";
  elements.mapDetailPanel.innerHTML = `
    <article class="map-detail-card">
      <div class="map-detail-body">
        <button type="button" class="map-back-button" id="map-back-button">Back to event list</button>
        <p class="map-detail-source">${sourceLabel}</p>
        <h4>${title}</h4>
        <ul>${details}</ul>
      </div>
    </article>
  `;
  const backButton = document.querySelector("#map-back-button");
  if (backButton) {
    backButton.addEventListener("click", () => renderMapDetail(null));
  }
}

async function geocodeAddress(address) {
  const query = (address || "").trim();
  if (!query) {
    return null;
  }
  const cacheKey = `geocode:v1:${query.toLowerCase()}`;
  try {
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
      return JSON.parse(cached);
    }
  } catch {
    // Ignore localStorage failures.
  }

  const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`;
  try {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return null;
    }
    const data = await response.json();
    if (!Array.isArray(data) || !data.length) {
      return null;
    }
    const result = {
      lat: Number(data[0].lat),
      lng: Number(data[0].lon),
    };
    if (Number.isFinite(result.lat) && Number.isFinite(result.lng)) {
      try {
        localStorage.setItem(cacheKey, JSON.stringify(result));
      } catch {
        // Ignore localStorage failures.
      }
      return result;
    }
  } catch {
    return null;
  }
  return null;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function enrichEventsWithCoordinates(events) {
  let geocodedAny = false;
  const limit = Math.min(events.length, 20);
  for (let index = 0; index < limit; index += 1) {
    const event = events[index];
    if (Number.isFinite(event.lat) && Number.isFinite(event.lng)) {
      continue;
    }
    const lookup = [event.venue, event.address, event.locality, event.region, "Cape Town", "South Africa"]
      .filter(Boolean)
      .join(", ");
    const coords = await geocodeAddress(lookup);
    if (coords) {
      event.lat = coords.lat;
      event.lng = coords.lng;
      geocodedAny = true;
    }
    await sleep(1000);
  }
  return geocodedAny;
}

function buildMapItems() {
  const mapItems = [];
  const payload = state.specialsPayload || {};
  const groups = payload.groups || [];
  const locations = payload.locations || {};

  const dayOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const today = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    timeZone: "Africa/Johannesburg",
  }).format(new Date());
  const todayIndex = dayOrder.indexOf(today);
  const rollingWeek = [...dayOrder.slice(todayIndex), ...dayOrder.slice(0, todayIndex)];

  const matchesTypeAndCategory = (types, categories) => {
    const typeList = types || [];
    const categoryList = categories || [];
    const typeOk = !state.availableMapTypes.length
      || (state.selectedMapTypes.size > 0 && typeList.some((tag) => state.selectedMapTypes.has(tag)));
    const categoryOk = !state.availableMapCategories.length
      || state.selectedMapCategories.size === 0
      || categoryList.some((tag) => state.selectedMapCategories.has(tag));
    return typeOk && categoryOk;
  };

  if (state.mapSources.places) {
    for (const location of Object.values(locations)) {
      if (matchesTypeAndCategory(location.types || location.tags || [], location.categories || [])) {
        mapItems.push(mapItemFromPlace(location));
      }
    }
  }

  if (state.mapSources.specials) {
    const specialsItems = specialsItemsForRange(groups, rollingWeek);
    const venueGroups = groupItemsByVenue(specialsItems)
      .map((group) => ({ ...group, location: locationForVenue(group.venue, locations) }))
      .filter((group) => group.location);
    for (const group of venueGroups) {
      if (matchesTypeAndCategory(group.location.types || group.location.tags || [], group.location.categories || [])) {
        mapItems.push(mapItemFromSpecialGroup(group));
      }
    }
  }

  if (state.mapSources.events) {
    for (const event of state.quicketEvents) {
      const mapItem = mapItemFromEvent(event);
      if (mapItem) {
        mapItems.push(mapItem);
      }
    }
  }

  return mapItems;
}

function renderMap() {
  if (!window.L) {
    elements.specialsMap.innerHTML = '<p class="empty">Map could not load.</p>';
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
    specialsMap.on("moveend zoomend", () => {
      if (!selectedMapItemKey) {
        renderMapEventList();
      }
    });
  }

  specialsMarkerLayer.clearLayers();
  mapMarkersByKey = new Map();
  const mapItems = buildMapItems();
  currentMapItems = mapItems;
  if (!mapItems.length) {
    const emptyText = "No mapped places for this filter.";
    const empty = L.popup({ closeButton: false, autoClose: false, closeOnClick: false })
      .setLatLng([-33.9249, 18.4241])
      .setContent(`<p class="map-empty-popup">${emptyText}</p>`)
      .openOn(specialsMap);
    selectedMapItemKey = "";
    renderMapDetail(null);
    setTimeout(() => specialsMap.invalidateSize(), 0);
    return;
  }

  specialsMap.closePopup();
  const bounds = [];
  for (const item of mapItems) {
    const title = item.url
      ? `<a href="${item.url}" target="_blank" rel="noreferrer">${item.title}</a>`
      : item.title;
    const details = item.details.map((detail) => `<li>${detail}</li>`).join("");
    const sourceLabel = item.source === "events" ? "Event" : item.source === "places" ? "Place" : "Special";
    const icon = item.source === "places"
      ? markerIcons.places
      : item.source === "events"
        ? markerIcons.events
        : markerIcons.specials;
    const marker = L.marker([item.lat, item.lng], { icon });
    if (item.source !== "specials") {
      marker.bindPopup(`<strong>${title}</strong><p>${sourceLabel}</p><ul>${details}</ul>`);
    }
    if (item.source === "specials" || item.source === "places") {
      mapMarkersByKey.set(`${item.source}:${venueKey(item.title)}`, marker);
    }
    marker.on("click", () => {
      selectedMapItemKey = mapItemKey(item);
      renderMapDetail(item);
    });
    marker.addTo(specialsMarkerLayer);
    bounds.push([item.lat, item.lng]);
  }

  if (!hasAutoFitMap || forceNextMapFit) {
    if (bounds.length === 1) {
      specialsMap.setView(bounds[0], 14);
    } else {
      specialsMap.fitBounds(bounds, { padding: [24, 24] });
    }
    hasAutoFitMap = true;
    forceNextMapFit = false;
  }
  if (selectedMapItemKey) {
    const selected = currentMapItems.find((item) => mapItemKey(item) === selectedMapItemKey);
    if (selected) {
      renderMapDetail(selected);
    } else {
      selectedMapItemKey = "";
      renderMapDetail(null);
    }
  } else {
    renderMapDetail(null);
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

  const rail = document.createElement("div");
  rail.className = "special-cards-rail";
  const track = document.createElement("div");
  track.className = "special-cards-track";

  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "special-empty";
    empty.textContent = "No specials listed.";
    track.append(empty);
    rail.append(track);
    section.append(rail);
    return section;
  }

  for (const item of items) {
    const card = document.createElement("article");
    card.className = "special-card";
    card.style.cursor = "pointer";
    card.addEventListener("click", () => {
      focusSpecialOnMap(item.venue || item.title || "");
    });

    const title = document.createElement("h5");
    title.textContent = item.venue || item.title || "Special";
    card.append(title);

    const details = document.createElement("p");
    const detailsText = item.details || item.deal || item.description || "";
    if (detailsText) {
      details.textContent = detailsText;
      card.append(details);
    }

    const price = document.createElement("p");
    const priceText = item.price || "";
    if (priceText) {
      price.textContent = priceText;
      card.append(price);
    }

    const time = document.createElement("p");
    const timeText = item.time || "";
    if (timeText) {
      time.textContent = timeText;
      card.append(time);
    }

    const daysText = formatDaysSummary(item.allDays || [day]) || day;
    if (daysText) {
      const days = document.createElement("p");
      days.textContent = daysText;
      card.append(days);
    }

    track.append(card);
  }

  rail.append(track);
  section.append(rail);
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

function showMyLocation() {
  if (!navigator.geolocation) {
    alert("Location is not available in this browser.");
    return;
  }
  if (!specialsMap) {
    renderMap();
  }
  if (myLocationMarker) {
    const markerPos = myLocationMarker.getLatLng();
    specialsMap.setView(markerPos, 13, { animate: true });
    myLocationMarker.openPopup();
  } else if (myLocationLatLng) {
    specialsMap.setView(myLocationLatLng, 13, { animate: true });
  }
  navigator.geolocation.getCurrentPosition(
    (position) => {
      const lat = position.coords.latitude;
      const lng = position.coords.longitude;
      myLocationLatLng = [lat, lng];
      if (myLocationMarker) {
        myLocationMarker.setLatLng(myLocationLatLng);
      } else {
        myLocationMarker = L.marker(myLocationLatLng, {
          icon: markerIcons.myLocation,
        }).bindPopup("<strong>You are here</strong>", { autoPan: false });
        myLocationMarker.addTo(specialsMap);
      }
      specialsMap.setView(myLocationLatLng, 13, { animate: true });
      myLocationMarker.openPopup();
    },
    () => {
      alert("Could not get your location. Check browser location permissions.");
    },
    {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 60000,
    },
  );
}

async function loadWeather() {
  try {
    const response = await fetch(WEATHER_PATH, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Could not load weather.");
    }
    const payload = await response.json();
    state.weatherPayload = payload;
    renderWeather(payload);
  } catch (error) {
    elements.weatherCards.innerHTML = `<p class="empty">${error.message}</p>`;
  }
}

async function loadMetadata() {
  try {
    const response = await fetch(METADATA_PATH, { cache: "no-store" });
    if (!response.ok) {
      setLastScrapedText("");
      return;
    }
    const payload = await response.json();
    setLastScrapedText(payload.last_scraped_at || payload.scraped_at || "");
  } catch {
    setLastScrapedText("");
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

async function loadQuicketEvents() {
  try {
    const response = await fetch(QUICKET_EVENTS_PATH, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Could not load ${QUICKET_EVENTS_PATH}`);
    }
    const events = await response.json();
    state.quicketEvents = Array.isArray(events) ? events : [];
    renderQuicketEvents(state.quicketEvents);
    renderMap();
    const changed = await enrichEventsWithCoordinates(state.quicketEvents);
    if (changed) {
      renderMap();
    }
  } catch (error) {
    elements.quicketEventsList.innerHTML = `<p class="empty">${error.message}</p>`;
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

for (const button of mapRangeButtons) {
  button.addEventListener("click", () => {
    clearCustomDateRange();
    state.specialsMapRange = button.dataset.range || "next-7";
    applyMapRangeChange();
  });
}

if (elements.customStartDate) {
  elements.customStartDate.addEventListener("change", (event) => {
    state.customStartDate = event.target.value || "";
    applyMapRangeChange();
  });
}

if (elements.customEndDate) {
  elements.customEndDate.addEventListener("change", (event) => {
    state.customEndDate = event.target.value || "";
    applyMapRangeChange();
  });
}

if (elements.customStartDateButton && elements.customStartDate) {
  elements.customStartDateButton.addEventListener("click", () => {
    if (typeof elements.customStartDate.showPicker === "function") {
      elements.customStartDate.showPicker();
    } else {
      elements.customStartDate.click();
    }
  });
}

if (elements.customEndDateButton && elements.customEndDate) {
  elements.customEndDateButton.addEventListener("click", () => {
    if (typeof elements.customEndDate.showPicker === "function") {
      elements.customEndDate.showPicker();
    } else {
      elements.customEndDate.click();
    }
  });
}

elements.mapSourcePlaces.addEventListener("change", (event) => {
  state.mapSources.places = event.target.checked;
  renderMap();
});

elements.mapSourceSpecials.addEventListener("change", (event) => {
  state.mapSources.specials = event.target.checked;
  renderMap();
});

elements.mapSourceEvents.addEventListener("change", (event) => {
  state.mapSources.events = event.target.checked;
  renderMap();
});

if (elements.locateMe) {
  elements.locateMe.addEventListener("click", showMyLocation);
}

if (elements.themeToggle) {
  elements.themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "dark" ? "light" : "dark";
    applyTheme(next);
    saveThemePreference(next);
  });
}

const storedTheme = loadThemePreference();
if (storedTheme) {
  applyTheme(storedTheme);
} else {
  applyTheme("light");
}

load();
setHeaderDate();
loadMetadata();
loadWeather();
loadReleases();
loadComingSoon();
loadSpecials();
loadQuicketEvents();
syncRangeButtons();


