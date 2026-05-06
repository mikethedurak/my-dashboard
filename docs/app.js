const CSV_PATH = "./data/one_piece/all_stores_missing_available.csv";
const NEW_CARDS_PATH = "./data/one_piece/new_missing_cards.json";
const RELEASES_PATH = "./data/release_radar/pahe_latest.json";
const COMING_SOON_PATH = "./data/release_radar/coming_soon.json";
const GAME_RELEASES_PATH = "./data/release_radar/game_releases.json";
const WATCHLIST_PATH = "./data/media/watchlist.json";
const GAMESLIST_PATH = "./data/media/gameslist.json";
const WATCHLIST_MOVIE_DETAILS_PATH = "./data/media/watchlist_movie_details.json";
const GAMES_DETAILS_PATH = "./data/media/games_details.json";
const NEWS_PATH = "./data/news/news.json";
const CONFIG_PATH = "../config.json";
const SPECIALS_PATH = "./data/events/specials.json";
const BANDSINTOWN_EVENTS_PATH = "./data/events/bandsintown_events.json";
const BANDSINTOWN_GENRE_FILTERS_PATH = "./data/events/bandsintown_genre_filters.json";
const QUICKET_EVENTS_PATH = "./data/events/quicket_events.json";
const WEATHER_PATH =
  "https://api.open-meteo.com/v1/forecast?latitude=-33.9249&longitude=18.4241&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=Africa%2FJohannesburg&forecast_days=7";
const HOLIDAYS_PATH = "https://date.nager.at/api/v3/publicholidays/{year}/ZA";
const METADATA_PATH = "./data/metadata.json";
const GOOGLE_CALENDAR_EVENTS_PATH = "./data/events/google_calendar_events.json";
const WEEK_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const WATCHLIST_MEDIA_CONFIG = {
  screen: { label: "Movies + Series", types: ["movie", "series"] },
  anime: { label: "Anime", types: ["anime_movie", "anime_series"] },
  games: { label: "Games", types: ["game_aaa", "game_indie", "game_coop", "game_couch_coop", "game_lan"] },
};
const WATCHLIST_TYPE_LABELS = {
  movie: "Movie",
  series: "Series",
  anime_movie: "Anime Movie",
  anime_series: "Anime Series",
  game_aaa: "Single-player",
  game_indie: "Indie",
  game_coop: "Co-op",
  game_couch_coop: "Couch Co-op",
  game_lan: "LAN",
};
const DEFAULT_OPINION_LEVELS = [
  { level: 1, key: "hated", defaultText: "Hated", text: "Hated", color: "#ffffff", aliases: ["Hated"] },
  { level: 2, key: "disliked", defaultText: "Disliked", text: "Disliked", color: "#16a34a", aliases: ["Disliked"] },
  { level: 3, key: "mixed", defaultText: "Mixed", text: "Mixed", color: "#1976d2", aliases: ["Mixed"] },
  { level: 4, key: "liked", defaultText: "Liked", text: "Liked", color: "#7c3aed", aliases: ["Liked"] },
  { level: 5, key: "loved", defaultText: "Loved", text: "Loved", color: "#ff8a00", aliases: ["Loved"] },
];
const NEWS_CATEGORIES = [
  { key: "all", label: "All" },
  { key: "global", label: "Global" },
  { key: "local", label: "Local" },
  { key: "games", label: "Games" },
  { key: "entertainment", label: "Entertainment" },
  { key: "climbing", label: "Climbing" },
];
const DASHBOARD_ORDER_STORAGE_KEY = "my-dashboard:module-order:v1";
const DASHBOARD_OPEN_STATE_STORAGE_KEY = "my-dashboard:module-open-state:v1";

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
  bandsintownEvents: [],
  bandsintownGenreFilters: [],
  selectedBandsintownGenre: "all",
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
  selectedEventCategories: new Set(),
  availableEventCategories: [],
  weatherPayload: null,
  customStartDate: "",
  customEndDate: "",
  watchlistActiveMedia: "screen",
  watchlistTypes: new Set(["movie"]),
  watchlistPayload: null,
  watchlistDetails: {},
  watchlistYearFilter: "all",
  watchlistCollectionFilter: "watched",
  watchlistGenreFilter: "all",
  watchlistSort: "default",
  watchlistOpinionFilter: "all",
  watchlistSearchFilter: "",
  opinionLevels: DEFAULT_OPINION_LEVELS,
  showOpinionIndicators: true,
  newsAllItems: [],
  newsItems: [],
  selectedNewsId: "",
  selectedNewsCategory: "all",
  isNewsExpanded: false,
  releaseItems: [],
};

const elements = {
  body: document.querySelector("#cards-body"),
  search: document.querySelector("#search"),
  storeFilter: document.querySelector("#store-filter"),
  rarityFilter: document.querySelector("#rarity-filter"),
  minPrice: document.querySelector("#min-price"),
  maxPrice: document.querySelector("#max-price"),
  watchlistOpinionIndicatorsToggle: document.querySelector("#watchlist-opinion-indicators-toggle"),
  releaseGrid: document.querySelector("#release-grid"),
  comingSoonGrid: document.querySelector("#coming-soon-grid"),
  gameReleaseGrid: document.querySelector("#game-release-grid"),
  gameComingSoonGrid: document.querySelector("#game-coming-soon-grid"),
  newsList: document.querySelector("#news-list"),
  newsDetail: document.querySelector("#news-detail"),
  newsCategoryButtons: document.querySelector("#news-category-buttons"),
  newsExpandToggle: document.querySelector("#news-expand-toggle"),
  watchlistCurrent: document.querySelector("#watchlist-current"),
  watchlistHistory: document.querySelector("#watchlist-history"),
  watchlistHistorySummary: document.querySelector("#watchlist-history-summary"),
  watchlistHistorySummaryLabel: document.querySelector("#watchlist-history-summary-label"),
  watchlistYearFilter: document.querySelector("#watchlist-year-filter"),
  watchlistCollectionFilter: document.querySelector("#watchlist-collection-filter"),
  watchlistSearchFilter: document.querySelector("#watchlist-search-filter"),
  watchlistGenreFilter: document.querySelector("#watchlist-genre-filter"),
  watchlistSort: document.querySelector("#watchlist-sort"),
  watchlistOpinionFilter: document.querySelector("#watchlist-opinion-filter"),
  watchlistCurrentSection: document.querySelector("#watchlist-current-section"),
  watchlistCurrentTitle: document.querySelector("#watchlist-current-title"),
  watchlistMediaButtons: document.querySelector("#watchlist-media-buttons"),
  watchlistCategoryButtons: document.querySelector("#watchlist-category-buttons"),
  watchlistDetailPanel: document.querySelector("#watchlist-detail-panel"),
  watchlistDetailContent: document.querySelector("#watchlist-detail-content"),
  watchlistDetailClose: document.querySelector("#watchlist-detail-close"),
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
  mapEventCategoryFilters: document.querySelector("#map-event-category-filters"),
  mapDetailPanel: document.querySelector("#map-detail-panel"),
  bandsintownEventsList: document.querySelector("#bandsintown-events-list"),
  quicketEventsList: document.querySelector("#quicket-events-list"),
  todayDate: document.querySelector("#today-date"),
  lastScraped: document.querySelector("#last-scraped"),
  themeToggle: document.querySelector("#theme-toggle"),
  layoutEditToggle: document.querySelector("#layout-edit-toggle"),
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

function displayDatePlain(value) {
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
  return `${day} ${monthName} ${year}`;
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

function renderPosters(container, items, emptyText, options = {}) {
  if (!items.length) {
    container.innerHTML = `<p class="empty">${emptyText}</p>`;
    return;
  }

  container.innerHTML = "";
  const interactiveRelease = Boolean(options.interactiveRelease);
  for (let index = 0; index < items.length; index += 1) {
    const item = items[index];
    const link = document.createElement("a");
    link.className = "poster-card";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    const ratingNumber = parseRatingValue(item.tmdb_rating || item.rating);
    const hoverRating = Number.isFinite(ratingNumber) ? `${ratingNumber.toFixed(1)}/10` : "";
    link.title = hoverRating ? `${item.title} | Rating: ${hoverRating}` : item.title;
    if (interactiveRelease) {
      link.dataset.releaseIndex = String(index);
    }

    const image = document.createElement("img");
    image.src = item.image;
    image.alt = item.title;
    image.loading = "lazy";
    image.title = link.title;

    const title = document.createElement("span");
    const releaseDate = displayDate(item.release_date);
    title.textContent = interactiveRelease ? item.title : releaseDate ? `${item.title} (${releaseDate})` : item.title;
    title.title = link.title;

    link.append(image, title);
    container.append(link);
  }
}

function parseRatingValue(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return Number.NaN;
  }
  const direct = Number(raw);
  if (Number.isFinite(direct)) {
    return direct;
  }
  const match = raw.match(/([0-9]+(?:\.[0-9]+)?)/);
  if (!match) {
    return Number.NaN;
  }
  const parsed = Number(match[1]);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function openReleaseDetail(item) {
  if (!elements.watchlistDetailPanel || !elements.watchlistDetailContent || !item) {
    return;
  }

  const title = String(item.title || "Movie").trim();
  const safeTitle = escapeHtml(title);
  const posterUrl = String(item.poster_url || item.image || "").trim();
  const ratingNumber = Number(item.tmdb_rating || item.rating);
  const ratingText = Number.isFinite(ratingNumber) ? `${ratingNumber.toFixed(1)}/10` : "";
  const releaseDate = displayDatePlain(String(item.release_date || "").trim());
  const runtimeValue = Number(item.runtime_minutes);
  const runtime = Number.isFinite(runtimeValue) && runtimeValue > 0 ? `${runtimeValue} min` : "";
  const genres = joinList(item.genres) || "";
  const directors = joinList(item.directors) || "Unknown";
  const actors = joinList(item.actors) || "Unknown";
  const description = stripHtmlTags(item.overview || "") || "No description yet.";
  const trailerUrl = String(item.trailer_url || "").trim();
  const tmdbUrl = String(item.tmdb_url || "").trim();
  const timingBits = [releaseDate, runtime].filter(Boolean);
  const posterHtml = posterUrl
    ? `<img class="watchlist-detail-poster" src="${posterUrl}" alt="${safeTitle} poster">`
    : '<div class="watchlist-detail-poster watchlist-entry-poster-empty">No poster</div>';
  const ratingHtml = ratingText ? `<p class="watchlist-detail-rating">${escapeHtml(ratingText)}</p>` : "";

  elements.watchlistDetailContent.innerHTML = `
    <div class="watchlist-detail-layout">
      ${posterHtml}
      <div class="watchlist-detail-body">
        <p class="watchlist-detail-kicker">Release Radar</p>
        <h3>${safeTitle}</h3>
        ${ratingHtml}
        ${timingBits.length ? `<p class="watchlist-detail-meta">${escapeHtml(timingBits.join(" • "))}</p>` : ""}
        ${genres ? `<p class="watchlist-detail-meta">${escapeHtml(genres)}</p>` : ""}
        <p class="watchlist-detail-description">${escapeHtml(description)}</p>
        <p><strong>Directors:</strong> ${escapeHtml(directors)}</p>
        <p><strong>Actors:</strong> ${escapeHtml(actors)}</p>
        <div class="watchlist-detail-links">
          ${trailerUrl ? `<a href="${trailerUrl}" target="_blank" rel="noreferrer">Trailer</a>` : ""}
          ${tmdbUrl ? `<a href="${tmdbUrl}" target="_blank" rel="noreferrer">TMDB</a>` : ""}
        </div>
      </div>
    </div>
  `;

  elements.watchlistDetailPanel.hidden = false;
  elements.watchlistDetailPanel.classList.add("is-open");
  elements.watchlistDetailPanel.classList.remove(
    "is-loved",
    "opinion-loved",
    "opinion-liked",
    "opinion-mixed",
    "opinion-disliked",
    "opinion-hated",
  );
  elements.watchlistDetailPanel.dataset.watchOpinion = "";
  document.body.classList.add("watchlist-detail-open");
}

function formatNewsDate(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "";
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return raw;
  }
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function safeNewsId(item, index) {
  const explicit = String(item?.id || "").trim();
  if (explicit) {
    return explicit;
  }
  const title = String(item?.title || "").trim().toLowerCase();
  const published = String(item?.published_at || item?.date || "").trim().toLowerCase();
  const source = String(item?.source || "").trim().toLowerCase();
  const fallback = `${title}|${published}|${source}`.replace(/\s+/g, "-");
  return fallback || `news-${index}`;
}

function normalizeNewsCategory(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function categoryThemeKey(item) {
  const category = normalizeNewsCategory(item?.category);
  if (NEWS_CATEGORIES.some((entry) => entry.key === category)) {
    return category;
  }
  return "global";
}

function newsMetaText(item) {
  return [item.source, item.category, formatNewsDate(item.published_at || item.date)].filter(Boolean).join(" • ");
}

function renderNewsCategoryControls() {
  if (!elements.newsCategoryButtons) {
    return;
  }
  elements.newsCategoryButtons.innerHTML = NEWS_CATEGORIES.map(
    (item) => `
      <button
        type="button"
        class="watchlist-category-button news-category-button news-category-${item.key}${state.selectedNewsCategory === item.key ? " is-selected" : ""}"
        data-news-category="${item.key}"
      >
        ${item.label}
      </button>
    `,
  ).join("");
}

function renderNewsDetail(item) {
  if (!elements.newsDetail) {
    return;
  }
  if (!item) {
    elements.newsDetail.innerHTML = '<p class="empty">Click a news article to read more.</p>';
    return;
  }

  const title = String(item.title || "Untitled article").trim();
  const summary = String(item.summary || "").trim();
  const body = String(item.body || item.content || "").trim();
  const url = String(item.url || "").trim();
  const imageUrl = String(item.image_url || item.image || "").trim();
  const tags = Array.isArray(item.tags) ? item.tags.filter(Boolean) : [];
  const tagHtml = tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("");
  const imageHtml = imageUrl
    ? `<img class="news-detail-image" src="${escapeHtml(imageUrl)}" alt="${escapeHtml(title)} image" loading="lazy">`
    : "";

  elements.newsDetail.innerHTML = `
    ${imageHtml}
    <div class="news-detail-body news-theme-${categoryThemeKey(item)}">
      <p class="news-meta">${escapeHtml(newsMetaText(item))}</p>
      <h3>${escapeHtml(title)}</h3>
      ${summary ? `<p class="news-summary">${escapeHtml(summary)}</p>` : ""}
      ${body ? `<p>${escapeHtml(body)}</p>` : ""}
      ${tagHtml ? `<div class="news-tags">${tagHtml}</div>` : ""}
      ${url ? `<a class="news-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">Open article</a>` : ""}
    </div>
  `;
}

function renderNews(items) {
  if (!elements.newsList) {
    return;
  }
  renderNewsCategoryControls();
  const normalized = Array.isArray(items) ? items : [];
  const filtered = state.selectedNewsCategory === "all"
    ? normalized
    : normalized.filter((item) => normalizeNewsCategory(item.category) === state.selectedNewsCategory);
  if (!filtered.length) {
    elements.newsList.innerHTML = '<p class="empty">No news articles found.</p>';
    renderNewsDetail(null);
    if (elements.newsExpandToggle) {
      elements.newsExpandToggle.hidden = true;
    }
    return;
  }

  state.newsItems = filtered.map((item, index) => ({ ...item, id: safeNewsId(item, index) }));
  if (!state.selectedNewsId || !state.newsItems.some((item) => item.id === state.selectedNewsId)) {
    state.selectedNewsId = state.newsItems[0].id;
  }

  elements.newsList.innerHTML = "";
  for (const item of state.newsItems) {
    const title = String(item.title || "Untitled article").trim();
    const summary = String(item.summary || "").trim();
    const selected = item.id === state.selectedNewsId;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `news-card news-theme-${categoryThemeKey(item)}${selected ? " is-selected" : ""}`;
    button.dataset.newsId = item.id;
    button.innerHTML = `
      <span class="news-meta">${escapeHtml(newsMetaText(item))}</span>
      <span class="news-card-title">${escapeHtml(title)}</span>
      ${summary ? `<span class="news-card-summary">${escapeHtml(summary)}</span>` : ""}
    `;
    elements.newsList.append(button);
  }

  if (elements.newsExpandToggle) {
    const canExpand = state.newsItems.length > 3;
    elements.newsExpandToggle.hidden = !canExpand;
    if (!canExpand) {
      state.isNewsExpanded = false;
    }
    elements.newsList.classList.toggle("is-expanded", state.isNewsExpanded && canExpand);
    elements.newsExpandToggle.textContent = state.isNewsExpanded ? "Retract" : "Expand";
  }

  renderNewsDetail(state.newsItems.find((item) => item.id === state.selectedNewsId));
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

function safeWatchTitle(item) {
  const sanitize = (value) =>
    String(value || "")
      .replace(/[🔥👍😐🤔👎💀]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  if (typeof item === "string") {
    return sanitize(item);
  }
  if (item && typeof item.title === "string") {
    return sanitize(item.title);
  }
  return "";
}

function normalizeOpinionKey(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[\s_-]+/g, "");
}

function configuredOpinionLevels() {
  return Array.isArray(state.opinionLevels) && state.opinionLevels.length
    ? state.opinionLevels
    : DEFAULT_OPINION_LEVELS;
}

function opinionLevelForValue(value) {
  const key = normalizeOpinionKey(value);
  if (!key) {
    return null;
  }
  return configuredOpinionLevels().find((level) =>
    [level.key, level.defaultText, level.text, ...(level.aliases || [])].some((candidate) => normalizeOpinionKey(candidate) === key),
  ) || null;
}

function opinionDisplayText(opinion) {
  const level = opinionLevelForValue(opinion);
  return level?.text || opinion || "";
}

function opinionCssKey(opinion) {
  const level = opinionLevelForValue(opinion);
  return level?.key || String(opinion || "").trim().toLowerCase();
}

function safeWatchType(item) {
  const rawType = typeof item === "object" && item ? String(item.type || "") : "";
  const lowered = rawType.toLowerCase().trim().replace(/[\s-]+/g, "_");
  if (lowered === "movie" || lowered === "movies") {
    return "movie";
  }
  if (lowered === "series" || lowered === "tv_series") {
    return "series";
  }
  if (lowered === "anime" || lowered === "anime_series") {
    return "anime_series";
  }
  if (lowered === "anime_movie" || lowered === "anime_movies") {
    return "anime_movie";
  }
  if (lowered === "aaa" || lowered === "game_aaa") {
    return "game_aaa";
  }
  if (lowered === "indie" || lowered === "game_indie") {
    return "game_indie";
  }
  if (lowered === "coop" || lowered === "co_op" || lowered === "game_coop") {
    return "game_coop";
  }
  if (lowered === "couch_coop" || lowered === "game_couch_coop") {
    return "game_couch_coop";
  }
  if (lowered === "lan" || lowered === "lan_games" || lowered === "game_lan") {
    return "game_lan";
  }
  return "";
}

function safeWatchOpinion(item) {
  if (!item || typeof item !== "object") {
    return "";
  }
  const raw = String(item.opinion || "").trim();
  const configured = opinionLevelForValue(raw);
  if (configured) {
    return configured.defaultText;
  }
  const title = String(item.title || "");
  if (title.includes("🔥")) {
    return "Loved";
  }
  if (title.includes("👍")) {
    return "Liked";
  }
  if (title.includes("🤔")) {
    return "Mixed";
  }
  if (title.includes("😐")) {
    return "Mixed";
  }
  if (title.includes("👎")) {
    return "Disliked";
  }
  if (title.includes("💀")) {
    return "Hated";
  }
  if (item.loved === true) {
    return "Loved";
  }
  return "";
}

function watchlistTypeWithOpinionLabel(type, opinion) {
  const typeLabel = escapeHtml(WATCHLIST_TYPE_LABELS[type] || "Title");
  if (!opinion || !state.showOpinionIndicators) {
    return typeLabel;
  }
  const safeOpinion = escapeHtml(opinionDisplayText(opinion));
  return `${typeLabel}<span class="watchlist-opinion-text opinion-${opinionCssKey(opinion)}">${safeOpinion}</span>`;
}

function watchlistHasType(type) {
  return state.watchlistTypes.has(type);
}

function mediaForType(type) {
  for (const [media, config] of Object.entries(WATCHLIST_MEDIA_CONFIG)) {
    if (config.types.includes(type)) {
      return media;
    }
  }
  return "screen";
}

function ensureWatchlistSelection() {
  if (state.watchlistTypes.size) {
    return;
  }
  const fallback = WATCHLIST_MEDIA_CONFIG[state.watchlistActiveMedia]?.types?.[0] || "movie";
  state.watchlistTypes = new Set([fallback]);
}

function toggleWatchlistType(type) {
  const media = mediaForType(type);
  if (media !== state.watchlistActiveMedia) {
    state.watchlistActiveMedia = media;
    state.watchlistTypes = new Set([type]);
    return;
  }
  state.watchlistTypes = new Set([type]);
}

function setWatchlistMedia(media) {
  if (!WATCHLIST_MEDIA_CONFIG[media]) {
    return;
  }
  if (state.watchlistActiveMedia === media) {
    ensureWatchlistSelection();
    return;
  }
  state.watchlistActiveMedia = media;
  const defaultType = WATCHLIST_MEDIA_CONFIG[media].types[0];
  state.watchlistTypes = new Set([defaultType]);
  state.watchlistGenreFilter = "all";
}

function renderWatchlistSelectorControls() {
  if (!elements.watchlistMediaButtons || !elements.watchlistCategoryButtons) {
    return;
  }

  elements.watchlistMediaButtons.innerHTML = Object.entries(WATCHLIST_MEDIA_CONFIG)
    .map(
      ([media, config]) => `
        <button
          id="watchlist-media-${media}"
          type="button"
          class="watchlist-media-button${state.watchlistActiveMedia === media ? " is-selected" : ""}"
          data-watch-media="${media}"
          aria-pressed="${state.watchlistActiveMedia === media ? "true" : "false"}"
        >${escapeHtml(config.label)}</button>
      `,
    )
    .join("");

  const activeConfig = WATCHLIST_MEDIA_CONFIG[state.watchlistActiveMedia] || WATCHLIST_MEDIA_CONFIG.screen;
  elements.watchlistCategoryButtons.innerHTML = activeConfig.types
    .map((type) => {
      const selected = watchlistHasType(type);
      return `
        <button
          type="button"
          class="watchlist-category-button${selected ? " is-selected" : ""}"
          data-watch-type="${type}"
          aria-pressed="${selected ? "true" : "false"}"
        >${escapeHtml(WATCHLIST_TYPE_LABELS[type] || type)}</button>
      `;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function stripHtmlTags(value) {
  const raw = String(value || "");
  if (!raw.includes("<") && !raw.includes("&")) {
    return raw.trim();
  }
  const unescaped = raw
    .replace(/&nbsp;/gi, " ")
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
  return unescaped
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function watchTypeLabel(item) {
  const type = safeWatchType(item);
  return WATCHLIST_TYPE_LABELS[type] || "Title";
}

function movieLookupKey(title) {
  return String(title || "")
    .toLowerCase()
    .replace(/[^\w\s]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function detailsLookupKey(type, title) {
  return `${type}:${movieLookupKey(title)}`;
}

function detailsForTitle(payload, type, title) {
  const details = state.watchlistDetails || {};
  const key = detailsLookupKey(type, title);
  if (!key) {
    return null;
  }
  const fallbackKey = type === "movie" ? movieLookupKey(title) : "";
  const value = details[key] || (fallbackKey ? details[fallbackKey] : null);
  if (!value || typeof value !== "object") {
    return null;
  }
  return value;
}

function watchlistRatingText(type, details = {}) {
  const isGame = String(type || "").startsWith("game_");
  if (isGame) {
    const rawMetacritic = details?.metacritic;
    const hasMetacritic = rawMetacritic !== null && rawMetacritic !== undefined && String(rawMetacritic).trim() !== "";
    const metacritic = Number(rawMetacritic);
    if (hasMetacritic && Number.isFinite(metacritic)) {
      return `${(metacritic / 10).toFixed(1)} / 10`;
    }
    const rawgRating = Number(details?.rating);
    if (Number.isFinite(rawgRating) && rawgRating > 0) {
      return `${(rawgRating * 2).toFixed(1)} / 10`;
    }
    return "";
  }
  const ratingValue = Number(details?.rating);
  if (!Number.isFinite(ratingValue)) {
    return "No rating";
  }
  return `${ratingValue.toFixed(1)} / 10`;
}

function renderWatchlistTitleCard(type, title, payload, item = null) {
  const mediaDetails = detailsForTitle(payload, type, title);
  const posterUrl = String(mediaDetails?.poster_url || "").trim();
  const ratingText = watchlistRatingText(type, mediaDetails || {});
  const safeTitle = escapeHtml(title);
  const opinion = safeWatchOpinion(item);
  const opinionKey = opinionCssKey(opinion);
  const opinionClass = opinion ? ` opinion-${opinionKey}` : "";

  const posterHtml = posterUrl
    ? `<img class="watchlist-entry-poster" src="${posterUrl}" alt="${safeTitle} poster" loading="lazy">`
    : '<div class="watchlist-entry-poster watchlist-entry-poster-empty">No poster</div>';

  const badgeLabel = watchlistTypeWithOpinionLabel(type, opinion);
  const ratingHtml = ratingText ? `<p class="watchlist-entry-rating">${ratingText}</p>` : "";
  return `
    <button
      type="button"
      class="watchlist-entry watchlist-current-entry watchlist-entry-button${opinion === "Loved" ? " is-loved" : ""}${opinionClass}"
      data-watch-type="${type}"
      data-watch-title="${encodeURIComponent(title)}"
      data-watch-opinion="${opinionKey}"
    >
      ${posterHtml}
      <div class="watchlist-entry-body">
        <p class="watchlist-entry-type">${badgeLabel}</p>
        <p class="watchlist-entry-title">${safeTitle}</p>
        ${ratingHtml}
      </div>
    </button>
  `;
}

function joinList(values) {
  if (!Array.isArray(values) || !values.length) {
    return "";
  }
  return values.filter(Boolean).join(", ");
}

function findWatchlistItem(payload, type, title) {
  const normalizedType = String(type || "").trim();
  const normalizedTitle = String(title || "").trim().toLowerCase();
  if (!normalizedType || !normalizedTitle) {
    return null;
  }

  const current = payload?.currently_watching || {};
  const gameBucket = current.games && typeof current.games === "object" ? current.games : {};
  const sourceByType = {
    movie: Array.isArray(current.movies) ? current.movies : [],
    series: Array.isArray(current.series) ? current.series : [],
    anime_series: Array.isArray(current.anime_series || current.anime) ? (current.anime_series || current.anime) : [],
    anime_movie: Array.isArray(current.anime_movies || current.anime_movie) ? (current.anime_movies || current.anime_movie) : [],
    game_aaa: Array.isArray(current.game_aaa || gameBucket.aaa) ? (current.game_aaa || gameBucket.aaa) : [],
    game_indie: Array.isArray(current.game_indie || gameBucket.indie) ? (current.game_indie || gameBucket.indie) : [],
    game_coop: Array.isArray(current.game_coop || gameBucket.coop) ? (current.game_coop || gameBucket.coop) : [],
    game_couch_coop: Array.isArray(current.game_couch_coop || gameBucket.couch_coop) ? (current.game_couch_coop || gameBucket.couch_coop) : [],
    game_lan: Array.isArray(current.game_lan || gameBucket.lan) ? (current.game_lan || gameBucket.lan) : [],
  };

  for (const item of sourceByType[normalizedType] || []) {
    if (safeWatchTitle(item).toLowerCase() === normalizedTitle) {
      return item;
    }
  }

  for (const group of payload?.history_by_year || []) {
    for (const entry of group?.entries || []) {
      if ((safeWatchType(entry) || "movie") !== normalizedType) {
        continue;
      }
      if (safeWatchTitle(entry).toLowerCase() === normalizedTitle) {
        return entry;
      }
    }
  }

  return null;
}

function watchlistHistoryLabel() {
  if (state.watchlistCollectionFilter === "backlog") {
    return "Backlog";
  }
  const labels = [...state.watchlistTypes].map((type) => WATCHLIST_TYPE_LABELS[type]).filter(Boolean);
  const gameOnly = [...state.watchlistTypes].every((type) => String(type || "").startsWith("game_"));
  const actionWord = gameOnly ? "played" : "watched";
  if (!labels.length) {
    return gameOnly ? "Played" : "Watched";
  }
  if (labels.length === 1) {
    return `${labels[0]} ${actionWord}`;
  }
  if (labels.length === 2) {
    return `${labels[0]} and ${labels[1]} ${actionWord}`;
  }
  return `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]} ${actionWord}`;
}

function collectionPrimaryLabel() {
  return state.watchlistActiveMedia === "games" ? "Games played" : "Movies watched";
}

function backlogEntries(payload) {
  const backlog = payload?.backlog || {};
  const entries = [];
  const byType = {
    movie: Array.isArray(backlog.movies) ? backlog.movies : [],
    series: Array.isArray(backlog.series) ? backlog.series : [],
    anime_movie: Array.isArray(backlog.anime_movies) ? backlog.anime_movies : [],
    anime_series: Array.isArray(backlog.anime_series) ? backlog.anime_series : [],
    game_aaa: Array.isArray(backlog.game_aaa) ? backlog.game_aaa : [],
    game_indie: Array.isArray(backlog.game_indie) ? backlog.game_indie : [],
    game_coop: Array.isArray(backlog.game_coop) ? backlog.game_coop : [],
    game_couch_coop: Array.isArray(backlog.game_couch_coop) ? backlog.game_couch_coop : [],
  };
  for (const [type, items] of Object.entries(byType)) {
    for (const item of items) {
      const title = safeWatchTitle(item);
      if (!title) {
        continue;
      }
      entries.push({ ...item, type, title });
    }
  }
  return entries;
}

function activeHistorySource(payload) {
  if (state.watchlistCollectionFilter === "backlog") {
    return [{ year: "Backlog", entries: backlogEntries(payload) }];
  }
  return Array.isArray(payload?.history_by_year) ? payload.history_by_year : [];
}

function compareReleaseDateDescending(left, right, payload) {
  const leftDate = String(detailsForTitle(payload, safeWatchType(left) || "movie", left.title)?.release_date || "");
  const rightDate = String(detailsForTitle(payload, safeWatchType(right) || "movie", right.title)?.release_date || "");
  return rightDate.localeCompare(leftDate);
}

function compareScoreDescending(left, right, payload) {
  const leftScore = Number(detailsForTitle(payload, safeWatchType(left) || "movie", left.title)?.rating || -1);
  const rightScore = Number(detailsForTitle(payload, safeWatchType(right) || "movie", right.title)?.rating || -1);
  if (rightScore !== leftScore) {
    return rightScore - leftScore;
  }
  return compareReleaseDateDescending(left, right, payload);
}

function watchlistGenres(payload) {
  if (!state.watchlistTypes.size) {
    return [];
  }
  const genres = new Set();
  for (const group of activeHistorySource(payload)) {
    for (const entry of group?.entries || []) {
      const entryType = safeWatchType(entry) || "movie";
      if (!watchlistHasType(entryType)) {
        continue;
      }
      const details = detailsForTitle(payload, entryType, safeWatchTitle(entry)) || {};
      for (const genre of details.genres || []) {
        if (genre) {
          genres.add(String(genre));
        }
      }
    }
  }
  return [...genres].sort((a, b) => a.localeCompare(b));
}

function watchlistYears(payload) {
  const years = [];
  const seen = new Set();
  for (const group of activeHistorySource(payload)) {
    const year = String(group?.year || "").trim();
    if (!year || year.toLowerCase() === "anime") {
      continue;
    }
    if (!seen.has(year)) {
      seen.add(year);
      years.push(year);
    }
  }
  return years;
}

function updateWatchlistFilterOptions(payload) {
  if (elements.watchlistHistorySummaryLabel) {
    elements.watchlistHistorySummaryLabel.textContent = watchlistHistoryLabel();
  }

  if (elements.watchlistYearFilter) {
    const years = watchlistYears(payload);
    if (!years.includes(state.watchlistYearFilter)) {
      state.watchlistYearFilter = "all";
    }
    elements.watchlistYearFilter.innerHTML = '<option value="all">All</option>';
    for (const year of years) {
      const option = document.createElement("option");
      option.value = year;
      option.textContent = year;
      if (state.watchlistYearFilter === year) {
        option.selected = true;
      }
      elements.watchlistYearFilter.append(option);
    }
    elements.watchlistYearFilter.disabled = state.watchlistCollectionFilter === "backlog";
  }

  if (elements.watchlistCollectionFilter) {
    const primaryLabel = collectionPrimaryLabel();
    elements.watchlistCollectionFilter.innerHTML = `
      <option value="watched">${escapeHtml(primaryLabel)}</option>
      <option value="backlog">Backlog</option>
    `;
    elements.watchlistCollectionFilter.value = state.watchlistCollectionFilter;
  }

  if (elements.watchlistGenreFilter) {
    const genres = watchlistGenres(payload);
    const genreDisabled = !genres.length;
    if (!genres.includes(state.watchlistGenreFilter)) {
      state.watchlistGenreFilter = "all";
    }
    elements.watchlistGenreFilter.innerHTML = '<option value="all">All genres</option>';
    for (const genre of genres) {
      const option = document.createElement("option");
      option.value = genre;
      option.textContent = genre;
      if (state.watchlistGenreFilter === genre) {
        option.selected = true;
      }
      elements.watchlistGenreFilter.append(option);
    }
    elements.watchlistGenreFilter.disabled = genreDisabled;
  }

  if (elements.watchlistSort) {
    elements.watchlistSort.value = state.watchlistSort;
  }

  if (elements.watchlistOpinionFilter) {
    const activeValue = state.watchlistOpinionFilter;
    elements.watchlistOpinionFilter.innerHTML = '<option value="all">All opinions</option>';
    for (const level of configuredOpinionLevels()) {
      const option = document.createElement("option");
      option.value = level.key;
      option.textContent = level.text;
      option.style.color = level.color;
      if (activeValue === level.key) {
        option.selected = true;
      }
      elements.watchlistOpinionFilter.append(option);
    }
    elements.watchlistOpinionFilter.value = state.watchlistOpinionFilter;
  }
}

function filteredWatchlistHistory(payload) {
  const results = [];
  const allEntries = [];
  for (const group of activeHistorySource(payload)) {
    const year = String(group?.year || "").trim();
    if (!year) {
      continue;
    }
    if (state.watchlistYearFilter !== "all" && state.watchlistYearFilter !== year) {
      continue;
    }

    let entries = Array.isArray(group?.entries) ? [...group.entries].reverse() : [];
    entries = entries
      .filter((entry) => watchlistHasType(safeWatchType(entry) || "movie"))
      .filter((entry) => {
        const searchTerm = state.watchlistSearchFilter.trim().toLowerCase();
        if (!searchTerm) {
          return true;
        }
        return safeWatchTitle(entry).toLowerCase().includes(searchTerm);
      })
      .filter((entry) => {
        if (state.watchlistOpinionFilter === "all") {
          return true;
        }
        return opinionCssKey(safeWatchOpinion(entry)) === state.watchlistOpinionFilter;
      })
      .filter((entry) => {
        const entryType = safeWatchType(entry) || "movie";
        if (state.watchlistGenreFilter === "all") {
          return true;
        }
        const details = detailsForTitle(payload, entryType, safeWatchTitle(entry)) || {};
        return (details.genres || []).includes(state.watchlistGenreFilter);
      });

    if (state.watchlistSort === "score") {
      entries.sort((left, right) => compareScoreDescending(left, right, payload));
    } else if (state.watchlistSort === "release_date") {
      entries.sort((left, right) => compareReleaseDateDescending(left, right, payload));
    }

    if (entries.length) {
      if (state.watchlistYearFilter === "all") {
        allEntries.push(...entries);
      } else {
        results.push({ year, entries });
      }
    }
  }

  if (state.watchlistYearFilter === "all") {
    if (!allEntries.length) {
      return [];
    }
    if (state.watchlistSort === "score") {
      allEntries.sort((left, right) => compareScoreDescending(left, right, payload));
    } else if (state.watchlistSort === "release_date") {
      allEntries.sort((left, right) => compareReleaseDateDescending(left, right, payload));
    }
    return [{ year: "All", entries: allEntries }];
  }
  return results;
}

function openWatchlistDetail(type, title) {
  if (!elements.watchlistDetailPanel || !elements.watchlistDetailContent || !state.watchlistPayload) {
    return;
  }
  const details = detailsForTitle(state.watchlistPayload, type, title) || {};
  const posterUrl = String(details.poster_url || "").trim();
  const ratingText = watchlistRatingText(type, details);
  const description = stripHtmlTags(details.description || details.overview || "") || "No description yet.";
  const directors = joinList(details.directors) || "Unknown";
  const actors = joinList(details.actors) || "Unknown";
  const publishers = joinList(details.publishers) || "Unknown";
  const developers = joinList(details.developers) || "Unknown";
  const platforms = joinList(details.platforms) || "";
  const playtimeValue = Number(details.playtime_hours);
  const playtime = Number.isFinite(playtimeValue) && playtimeValue > 0 ? `${playtimeValue}h playtime` : "";
  const genres = joinList(details.genres) || "";
  const releaseDate = displayDatePlain(String(details.release_date || "").trim());
  const runtime = Number.isFinite(Number(details.runtime_minutes)) ? `${Number(details.runtime_minutes)} min` : "";
  const seasonsCount = Number.isFinite(Number(details.number_of_seasons)) ? Number(details.number_of_seasons) : 0;
  const seasonsText = seasonsCount > 0 ? `${seasonsCount} ${seasonsCount === 1 ? "season" : "seasons"}` : "";
  const trailerUrl = String(details.trailer_url || "").trim();
  const tmdbUrl = String(details.tmdb_url || "").trim();
  const rawgUrl = String(details.rawg_url || "").trim();
  const websiteUrl = String(details.website_url || "").trim();
  const safeTitle = escapeHtml(title);
  const sourceItem = findWatchlistItem(state.watchlistPayload, type, title);
  const opinion = safeWatchOpinion(sourceItem);
  const opinionKey = opinionCssKey(opinion);
  const opinionClass = opinion ? ` opinion-${opinionKey}` : "";
  const safeLabel = watchlistTypeWithOpinionLabel(type, opinion);
  const isSeriesLike = type === "series" || type === "anime_series";
  const isMovieLike = type === "movie" || type === "anime_movie";
  const isGameLike = type.startsWith("game_");
  const timingBits = [
    releaseDate,
    isMovieLike ? runtime : isSeriesLike ? seasonsText : "",
    isGameLike ? playtime : "",
  ].filter(Boolean);
  const genreLine = genres;
  const posterHtml = posterUrl
    ? `<img class="watchlist-detail-poster" src="${posterUrl}" alt="${safeTitle} poster">`
    : '<div class="watchlist-detail-poster watchlist-entry-poster-empty">No poster</div>';
  const ratingHtml = ratingText ? `<p class="watchlist-detail-rating">${escapeHtml(ratingText)}</p>` : "";

  elements.watchlistDetailContent.innerHTML = `
    <div class="watchlist-detail-layout">
      ${posterHtml}
      <div class="watchlist-detail-body">
        <p class="watchlist-detail-kicker">${safeLabel}</p>
        <h3>${safeTitle}</h3>
        ${ratingHtml}
        ${timingBits.length ? `<p class="watchlist-detail-meta">${escapeHtml(timingBits.join(" • "))}</p>` : ""}
        ${genreLine ? `<p class="watchlist-detail-meta">${escapeHtml(genreLine)}</p>` : ""}
        <p class="watchlist-detail-description">${escapeHtml(description)}</p>
        ${
          isGameLike
            ? `<p><strong>Publishers:</strong> ${escapeHtml(publishers)}</p>
               <p><strong>Developers:</strong> ${escapeHtml(developers)}</p>
               ${platforms ? `<p><strong>Platforms:</strong> ${escapeHtml(platforms)}</p>` : ""}`
            : `<p><strong>${isMovieLike ? "Directors" : "Creators"}:</strong> ${escapeHtml(directors)}</p>
               <p><strong>Actors:</strong> ${escapeHtml(actors)}</p>`
        }
        <div class="watchlist-detail-links">
          ${trailerUrl ? `<a href="${trailerUrl}" target="_blank" rel="noreferrer">Trailer</a>` : ""}
          ${tmdbUrl ? `<a href="${tmdbUrl}" target="_blank" rel="noreferrer">TMDB</a>` : ""}
          ${rawgUrl ? `<a href="${rawgUrl}" target="_blank" rel="noreferrer">RAWG</a>` : ""}
          ${websiteUrl ? `<a href="${websiteUrl}" target="_blank" rel="noreferrer">Website</a>` : ""}
        </div>
      </div>
    </div>
  `;
  elements.watchlistDetailPanel.hidden = false;
  elements.watchlistDetailPanel.classList.add("is-open");
  elements.watchlistDetailPanel.classList.toggle("is-loved", opinion === "Loved");
  elements.watchlistDetailPanel.classList.remove(
    "opinion-loved",
    "opinion-liked",
    "opinion-mixed",
    "opinion-disliked",
    "opinion-hated",
  );
  if (opinionClass) {
    elements.watchlistDetailPanel.classList.add(opinionClass.trim());
  }
  elements.watchlistDetailPanel.dataset.watchOpinion = opinionKey;
  document.body.classList.add("watchlist-detail-open");
}

function renderWatchlistCurrent(payload) {
  const current = payload?.currently_watching || {};
  const searchTerm = state.watchlistSearchFilter.trim().toLowerCase();
  const asItems = (value) => (Array.isArray(value) ? value.filter(Boolean) : []);
  const gameBucket = current.games && typeof current.games === "object" ? current.games : {};
  const sourceByType = {
    movie: asItems(current.movies),
    series: asItems(current.series),
    anime_series: asItems(current.anime_series || current.anime),
    anime_movie: asItems(current.anime_movies || current.anime_movie),
    game_aaa: asItems(current.game_aaa || gameBucket.aaa),
    game_indie: asItems(current.game_indie || gameBucket.indie),
    game_coop: asItems(current.game_coop || gameBucket.coop),
    game_couch_coop: asItems(current.game_couch_coop || gameBucket.couch_coop),
    game_lan: asItems(current.game_lan || gameBucket.lan),
  };
  const sections = [...state.watchlistTypes]
    .map((type) => ({
      type,
      heading: WATCHLIST_TYPE_LABELS[type] || "Titles",
      items: (sourceByType[type] || []).filter((item) => !searchTerm || safeWatchTitle(item).toLowerCase().includes(searchTerm)),
    }))
    .filter((section) => section.items.length);
  if (elements.watchlistCurrentTitle) {
    const gameOnly = [...state.watchlistTypes].every((type) => String(type || "").startsWith("game_"));
    elements.watchlistCurrentTitle.textContent = gameOnly ? "Currently playing" : "Currently watching";
  }

  if (!sections.length) {
    if (elements.watchlistCurrentSection) {
      elements.watchlistCurrentSection.hidden = true;
    }
    elements.watchlistCurrent.innerHTML = "";
    return;
  }
  if (elements.watchlistCurrentSection) {
    elements.watchlistCurrentSection.hidden = false;
  }

  elements.watchlistCurrent.innerHTML = sections
    .map((section) => {
      const cards = section.items
        .map((title) => {
          const safeTitle = safeWatchTitle(title);
          return renderWatchlistTitleCard(section.type, safeTitle, payload, title);
        })
        .join("");
      return `
        <article class="watchlist-current-card">
          <h4>${section.heading}</h4>
          <div class="watchlist-current-grid">${cards}</div>
        </article>
      `;
    })
    .join("");
}

function renderWatchlistHistory(payload) {
  updateWatchlistFilterOptions(payload);
  const history = filteredWatchlistHistory(payload);
  if (!history.length) {
    elements.watchlistHistory.innerHTML = '<p class="empty">No watch history found.</p>';
    return;
  }

  elements.watchlistHistory.innerHTML = "";
  for (const group of history) {
    const year = String(group?.year || "").trim();
    const entries = Array.isArray(group?.entries) ? group.entries : [];
    if (!year || !entries.length) {
      continue;
    }

    const section = document.createElement("section");
    section.className = "watchlist-year-group";

    const heading = document.createElement("h4");
    heading.className = "watchlist-year-heading";
    heading.textContent = `${year} (${entries.length})`;
    section.append(heading);

    const list = document.createElement("div");
    list.className = "watchlist-year-list";
    for (const entry of entries) {
      const entryType = safeWatchType(entry) || "movie";
      if (!watchlistHasType(entryType)) {
        continue;
      }
      const title = safeWatchTitle(entry);
      if (!title) {
        continue;
      }
      const cardHtml = renderWatchlistTitleCard(entryType, title, payload, entry);
      const wrapper = document.createElement("div");
      wrapper.innerHTML = cardHtml;
      const card = wrapper.firstElementChild;
      if (!card) {
        continue;
      }
      list.append(card);
    }

    if (!list.children.length) {
      continue;
    }
    section.append(list);
    elements.watchlistHistory.append(section);
  }

  if (!elements.watchlistHistory.children.length) {
    elements.watchlistHistory.innerHTML = '<p class="empty">No watch history found.</p>';
  }
}

function renderWatchlistSelectorState() {
  if (!elements.watchlistMediaButtons || !elements.watchlistCategoryButtons) {
    return;
  }

  elements.watchlistMediaButtons.querySelectorAll(".watchlist-media-button").forEach((button) => {
    const media = button.dataset.watchMedia || "";
    const selected = media === state.watchlistActiveMedia;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
  });

  elements.watchlistCategoryButtons.querySelectorAll(".watchlist-category-button").forEach((button) => {
    const type = button.dataset.watchType || "";
    const selected = watchlistHasType(type);
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
  });
}

function renderWatchlistAll() {
  if (!state.watchlistPayload) {
    return;
  }
  document.documentElement.classList.toggle("hide-watch-opinion-indicators", !state.showOpinionIndicators);
  renderWatchlistSelectorControls();
  renderWatchlistSelectorState();
  renderWatchlistCurrent(state.watchlistPayload);
  renderWatchlistHistory(state.watchlistPayload);
}

function loadOpinionLevelsFromEnv(payload) {
  const configured = payload?.opinion_levels;
  if (!configured || typeof configured !== "object") {
    state.opinionLevels = DEFAULT_OPINION_LEVELS;
    return;
  }
  state.opinionLevels = DEFAULT_OPINION_LEVELS.map((fallback) => {
    const value = configured[`level${fallback.level}`] || {};
    return {
      ...fallback,
      defaultText: String(value.default_text || fallback.defaultText).trim() || fallback.defaultText,
      text: String(value.text || fallback.text).trim() || fallback.text,
      color: String(value.color || fallback.color).trim() || fallback.color,
      aliases: [fallback.defaultText, value.default_text].filter(Boolean),
    };
  });
}

function applyOpinionLevelStyles() {
  const root = document.documentElement;
  for (const level of configuredOpinionLevels()) {
    root.style.setProperty(`--opinion-${level.key}`, level.color);
    root.style.setProperty(`--opinion-level-${level.level}`, level.color);
  }
}

async function loadWatchlist() {
  try {
    const [envResponse, watchlistResponse, gameslistResponse, detailsResponse, gamesDetailsResponse] = await Promise.all([
      fetch(CONFIG_PATH, { cache: "no-store" }),
      fetch(WATCHLIST_PATH, { cache: "no-store" }),
      fetch(GAMESLIST_PATH, { cache: "no-store" }),
      fetch(WATCHLIST_MOVIE_DETAILS_PATH, { cache: "no-store" }),
      fetch(GAMES_DETAILS_PATH, { cache: "no-store" }),
    ]);
    if (envResponse.ok) {
      try {
        loadOpinionLevelsFromEnv(await envResponse.json());
      } catch {
        loadOpinionLevelsFromEnv({});
      }
    } else {
      loadOpinionLevelsFromEnv({});
    }
    applyOpinionLevelStyles();
    if (!watchlistResponse.ok) {
      throw new Error(`Could not load ${WATCHLIST_PATH}`);
    }
    const watchlistPayload = await watchlistResponse.json();
    const gamesPayload = gameslistResponse.ok ? await gameslistResponse.json() : {};
    const mergedPayload = { ...(watchlistPayload || {}) };
    const mergedCurrent = { ...(mergedPayload.currently_watching || {}) };
    const gamesCurrent = gamesPayload?.currently_watching?.games;
    if (gamesCurrent && typeof gamesCurrent === "object") {
      mergedCurrent.games = gamesCurrent;
    }
    mergedPayload.currently_watching = mergedCurrent;
    const watchHistory = Array.isArray(mergedPayload.history_by_year) ? mergedPayload.history_by_year : [];
    const gamesHistory = Array.isArray(gamesPayload?.history_by_year) ? gamesPayload.history_by_year : [];
    mergedPayload.history_by_year = [...watchHistory, ...gamesHistory];
    const watchBacklog = mergedPayload.backlog && typeof mergedPayload.backlog === "object" ? mergedPayload.backlog : {};
    const gamesBacklog = gamesPayload?.backlog && typeof gamesPayload.backlog === "object" ? gamesPayload.backlog : {};
    mergedPayload.backlog = { ...watchBacklog, ...gamesBacklog };
    state.watchlistPayload = mergedPayload;
    const movieDetails = detailsResponse.ok ? await detailsResponse.json() : {};
    const gameDetails = gamesDetailsResponse.ok ? await gamesDetailsResponse.json() : {};
    state.watchlistDetails = {
      ...(movieDetails && typeof movieDetails === "object" ? movieDetails : {}),
      ...(gameDetails && typeof gameDetails === "object" ? gameDetails : {}),
    };
    renderWatchlistAll();
  } catch (error) {
    elements.watchlistCurrent.innerHTML = `<p class="empty">${error.message}</p>`;
    elements.watchlistHistory.innerHTML = `<p class="empty">${error.message}</p>`;
  }
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

function normalizeModuleId(label) {
  return String(label || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function getDashboardSections() {
  return [...document.querySelectorAll("main > details.dashboard-section")];
}

function ensureDashboardSectionIds() {
  for (const section of getDashboardSections()) {
    if (section.dataset.moduleId) {
      continue;
    }
    const summaryLabel = section.querySelector("summary span")?.textContent || "";
    section.dataset.moduleId = normalizeModuleId(summaryLabel);
  }
}

function loadDashboardOrderPreference() {
  try {
    const raw = localStorage.getItem(DASHBOARD_ORDER_STORAGE_KEY) || "";
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((value) => typeof value === "string" && value) : [];
  } catch {
    return [];
  }
}

function saveDashboardOrderPreference() {
  try {
    const orderedIds = getDashboardSections().map((section) => section.dataset.moduleId || "").filter(Boolean);
    localStorage.setItem(DASHBOARD_ORDER_STORAGE_KEY, JSON.stringify(orderedIds));
  } catch {
    // Ignore localStorage failures.
  }
}

function applyDashboardOrderPreference() {
  ensureDashboardSectionIds();
  const orderedIds = loadDashboardOrderPreference();
  if (!orderedIds.length) {
    return;
  }
  const main = document.querySelector("main");
  if (!main) {
    return;
  }
  const sectionMap = new Map(getDashboardSections().map((section) => [section.dataset.moduleId, section]));
  for (const id of orderedIds) {
    const section = sectionMap.get(id);
    if (section) {
      main.appendChild(section);
    }
  }
}

function loadDashboardOpenStatePreference() {
  try {
    const raw = localStorage.getItem(DASHBOARD_OPEN_STATE_STORAGE_KEY) || "";
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveDashboardOpenStatePreference() {
  try {
    const payload = {};
    for (const section of getDashboardSections()) {
      const id = section.dataset.moduleId || "";
      if (!id) {
        continue;
      }
      payload[id] = Boolean(section.open);
    }
    localStorage.setItem(DASHBOARD_OPEN_STATE_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Ignore localStorage failures.
  }
}

function applyDashboardOpenStatePreference() {
  ensureDashboardSectionIds();
  const openStateById = loadDashboardOpenStatePreference();
  for (const section of getDashboardSections()) {
    const id = section.dataset.moduleId || "";
    if (!id || !(id in openStateById)) {
      continue;
    }
    section.open = Boolean(openStateById[id]);
  }
}

function setLayoutEditMode(isEditing) {
  document.body.classList.toggle("is-editing-layout", Boolean(isEditing));
  if (elements.layoutEditToggle) {
    elements.layoutEditToggle.textContent = isEditing ? "Done editing" : "Edit mode";
    elements.layoutEditToggle.setAttribute("aria-pressed", isEditing ? "true" : "false");
  }
}

function moveDashboardSection(section, direction) {
  const sections = getDashboardSections();
  const currentIndex = sections.indexOf(section);
  if (currentIndex < 0) {
    return;
  }
  const nextIndex = currentIndex + direction;
  if (nextIndex < 0 || nextIndex >= sections.length) {
    return;
  }
  const main = document.querySelector("main");
  if (!main) {
    return;
  }
  const target = sections[nextIndex];
  if (direction < 0) {
    main.insertBefore(section, target);
  } else {
    main.insertBefore(target, section);
  }
  saveDashboardOrderPreference();
}

function setupDashboardSectionEditor() {
  ensureDashboardSectionIds();
  applyDashboardOrderPreference();
  applyDashboardOpenStatePreference();

  for (const section of getDashboardSections()) {
    const summary = section.querySelector("summary");
    if (!summary || summary.querySelector(".module-edit-controls")) {
      continue;
    }

    const controls = document.createElement("span");
    controls.className = "module-edit-controls";

    const upButton = document.createElement("button");
    upButton.type = "button";
    upButton.className = "module-order-button";
    upButton.textContent = "Up";
    upButton.setAttribute("aria-label", "Move module up");
    upButton.title = "Move module up";

    const downButton = document.createElement("button");
    downButton.type = "button";
    downButton.className = "module-order-button";
    downButton.textContent = "Down";
    downButton.setAttribute("aria-label", "Move module down");
    downButton.title = "Move module down";

    for (const button of [upButton, downButton]) {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
      });
    }

    upButton.addEventListener("click", () => {
      moveDashboardSection(section, -1);
    });
    downButton.addEventListener("click", () => {
      moveDashboardSection(section, 1);
    });

    controls.appendChild(upButton);
    controls.appendChild(downButton);
    summary.appendChild(controls);

    section.addEventListener("toggle", () => {
      saveDashboardOpenStatePreference();
    });
  }

  setLayoutEditMode(false);
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
          <p class="weather-temp">${Math.round(item.max)}\u00B0 / ${Math.round(item.min)}\u00B0</p>
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
          <p class="weather-temp">${Math.round(item.max)}\u00B0 / ${Math.round(item.min)}\u00B0</p>
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

function categorizeEvent(title, venue) {
  const text = `${title || ""} ${venue || ""}`.toLowerCase();
  const categories = [];
  if (/concert|live music|\bband\b|jazz|orchestra|choir|\bsinger\b|dj set|\btour\b/.test(text)) categories.push("Music");
  if (/comedy|stand.?up|comedian/.test(text)) categories.push("Comedy");
  if (/\brun\b|\brace\b|cycling|triathlon|yoga|fitness|marathon|trail|\bhike\b|climb/.test(text)) categories.push("Sports");
  if (/museum|gallery|exhibition|\bart\b|heritage|culture/.test(text)) categories.push("art");
  if (/market|food festival|taste|beer fest|wine fest|brunch fest/.test(text)) categories.push("food");
  if (/\bparty\b|rooftop|nightlife|nightclub|\bdance\b/.test(text)) categories.push("club");
  if (/festival|carnival|\bfair\b/.test(text)) categories.push("festival");
  if (/\bkids?\b|family|children/.test(text)) categories.push("family");
  if (/\blan\b|gaming|esports|game jam/.test(text)) categories.push("gaming");
  if (/theatre|theater|\bplay\b|performance|drama/.test(text)) categories.push("theatre");
  return categories;
}

function renderEventCategoryFilters() {
  const allCategories = [];
  for (const event of state.quicketEvents) {
    const cats = event.categories?.length ? event.categories : categorizeEvent(event.title, event.venue);
    for (const cat of cats) allCategories.push(cat);
  }
  const categories = unique(allCategories);
  state.availableEventCategories = categories;
  state.selectedEventCategories = syncSelectedWithAvailable(state.selectedEventCategories, categories, false);

  renderFilterCheckboxes(
    elements.mapEventCategoryFilters,
    categories,
    state.selectedEventCategories,
    "No event categories yet.",
    (tag, checked) => {
      if (checked) {
        state.selectedEventCategories.add(tag);
      } else {
        state.selectedEventCategories.delete(tag);
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

function renderBandsintownEvents(events) {
  if (!elements.bandsintownEventsList) {
    return;
  }
  if (!events.length) {
    elements.bandsintownEventsList.innerHTML = '<p class="empty">No Bandsintown concerts found.</p>';
    return;
  }

  elements.bandsintownEventsList.innerHTML = "";

  const configured = Array.isArray(state.bandsintownGenreFilters) ? state.bandsintownGenreFilters : [];
  const discovered = unique(
    events.flatMap((event) => Array.isArray(event.genre_tags) ? event.genre_tags : []),
  );
  const configuredFiltered = configured.filter((genre) => discovered.includes(genre));
  const genres = configuredFiltered.length ? configuredFiltered : discovered;
  const availableKeys = new Set(["all", ...genres.map((genre) => normalizeGenreKey(genre))]);
  if (!availableKeys.has(state.selectedBandsintownGenre)) {
    state.selectedBandsintownGenre = "all";
  }

  const genreControls = document.createElement("div");
  genreControls.className = "watchlist-category-buttons bandsintown-genre-buttons";
  const allButton = document.createElement("button");
  allButton.type = "button";
  allButton.className = `watchlist-category-button bandsintown-genre-button${state.selectedBandsintownGenre === "all" ? " is-selected" : ""}`;
  allButton.dataset.bandsintownGenre = "all";
  allButton.textContent = "All";
  genreControls.append(allButton);
  for (const genre of genres) {
    const key = normalizeGenreKey(genre);
    const button = document.createElement("button");
    button.type = "button";
    button.className = `watchlist-category-button bandsintown-genre-button${state.selectedBandsintownGenre === key ? " is-selected" : ""}`;
    button.dataset.bandsintownGenre = key;
    button.textContent = genre;
    genreControls.append(button);
  }

  const title = document.createElement("h4");
  title.className = "events-rail-title";
  title.textContent = "Bandsintown concerts";

  const rail = document.createElement("div");
  rail.className = "events-cards-rail";
  const track = document.createElement("div");
  track.className = "events-cards-track";

  const filtered = state.selectedBandsintownGenre === "all"
    ? events
    : events.filter((event) =>
      (Array.isArray(event.genre_tags) ? event.genre_tags : [])
        .map((genre) => normalizeGenreKey(genre))
        .includes(state.selectedBandsintownGenre),
    );
  filtered.sort(compareBandsintownDateAsc);

  if (!filtered.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No concerts found for this genre.";
    track.append(empty);
  } else {
    for (const event of filtered) {
      const card = document.createElement("a");
      card.className = "bandsintown-event-card";
      card.href = event.url;
      card.target = "_blank";
      card.rel = "noreferrer";

      if (event.image) {
        const image = document.createElement("img");
        image.src = event.image;
        image.alt = event.title || "Bandsintown concert";
        image.loading = "lazy";
        card.append(image);
      }

      const body = document.createElement("div");
      body.className = "bandsintown-event-body";

      const date = document.createElement("span");
      date.className = "event-date";
      date.textContent = event.start ? displayDateTime(event.start) : event.date_text || "";

      const eventTitle = document.createElement("strong");
      eventTitle.textContent = event.title || "Untitled concert";

      const venue = document.createElement("span");
      venue.className = "event-venue";
      venue.textContent = [event.venue, event.locality].filter(Boolean).join(", ");

      body.append(date, eventTitle, venue);
      card.append(body);
      track.append(card);
    }
  }

  rail.append(track);
  elements.bandsintownEventsList.append(title, genreControls, rail);
}

function normalizeGenreKey(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function compareBandsintownDateAsc(left, right) {
  const leftTime = Date.parse(String(left?.start || ""));
  const rightTime = Date.parse(String(right?.start || ""));
  const leftHas = Number.isFinite(leftTime);
  const rightHas = Number.isFinite(rightTime);
  if (leftHas && rightHas) {
    return leftTime - rightTime;
  }
  if (leftHas) {
    return -1;
  }
  if (rightHas) {
    return 1;
  }
  const leftDateText = String(left?.date_text || "").trim().toLowerCase();
  const rightDateText = String(right?.date_text || "").trim().toLowerCase();
  return leftDateText.localeCompare(rightDateText);
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
    categories: event.categories?.length ? event.categories : categorizeEvent(event.title, event.venue),
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
        const eventCategoryOk = !state.availableEventCategories.length
          || state.selectedEventCategories.size === 0
          || mapItem.categories.some((tag) => state.selectedEventCategories.has(tag));
        if (eventCategoryOk) {
          mapItems.push(mapItem);
        }
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
    const icon = item.source === "places"
      ? markerIcons.places
      : item.source === "events"
        ? markerIcons.events
        : markerIcons.specials;
    const marker = L.marker([item.lat, item.lng], { icon });
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
    const items = Array.isArray(payload.items) ? payload.items : [];
    state.releaseItems = items;
    renderPosters(elements.releaseGrid, items, "No releases found.", { interactiveRelease: true });
  } catch (error) {
    state.releaseItems = [];
    elements.releaseGrid.innerHTML = `<p class="empty">${error.message}</p>`;
  }
}

async function loadNews() {
  if (!elements.newsList) {
    return;
  }
  try {
    const response = await fetch(NEWS_PATH, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Could not load ${NEWS_PATH}`);
    }
    const payload = await response.json();
    state.newsAllItems = Array.isArray(payload.items) ? payload.items : [];
    renderNews(state.newsAllItems);
  } catch (error) {
    elements.newsList.innerHTML = `<p class="empty">${error.message}</p>`;
    renderNewsDetail(null);
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
        });
        myLocationMarker.addTo(specialsMap);
      }
      specialsMap.setView(myLocationLatLng, 13, { animate: true });
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
    const items = Array.isArray(payload.items) ? [...payload.items] : [];
    items.sort((left, right) => {
      const leftDate = String(left?.release_date || "");
      const rightDate = String(right?.release_date || "");
      if (!leftDate && !rightDate) {
        return 0;
      }
      if (!leftDate) {
        return 1;
      }
      if (!rightDate) {
        return -1;
      }
      return leftDate.localeCompare(rightDate);
    });
    renderPosters(elements.comingSoonGrid, items, "No coming soon movies found.");
  } catch (error) {
    elements.comingSoonGrid.innerHTML = `<p class="empty">${error.message}</p>`;
  }
}

async function loadGameReleases() {
  try {
    const response = await fetch(GAME_RELEASES_PATH, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Could not load ${GAME_RELEASES_PATH}`);
    }
    const payload = await response.json();
    const allItems = Array.isArray(payload.items) ? [...payload.items] : [];
    const newReleases = Array.isArray(payload.new_releases) ? [...payload.new_releases] : [];
    const comingSoon = Array.isArray(payload.coming_soon) ? [...payload.coming_soon] : [];
    const hasSplitBuckets = newReleases.length || comingSoon.length;

    const sortByDateAsc = (items) => items.sort((left, right) => {
      const leftDate = String(left?.release_date || "");
      const rightDate = String(right?.release_date || "");
      if (!leftDate && !rightDate) {
        return 0;
      }
      if (!leftDate) {
        return 1;
      }
      if (!rightDate) {
        return -1;
      }
      return leftDate.localeCompare(rightDate);
    });
    const sortByDateDesc = (items) => items.sort((left, right) => {
      const leftDate = String(left?.release_date || "");
      const rightDate = String(right?.release_date || "");
      if (!leftDate && !rightDate) {
        return 0;
      }
      if (!leftDate) {
        return 1;
      }
      if (!rightDate) {
        return -1;
      }
      return rightDate.localeCompare(leftDate);
    });

    let releasedItems = [];
    let upcomingItems = [];
    if (hasSplitBuckets) {
      releasedItems = sortByDateDesc(newReleases);
      upcomingItems = sortByDateAsc(comingSoon);
    } else {
      sortByDateAsc(allItems);
      const today = new Date();
      for (const item of allItems) {
        const rawDate = String(item?.release_date || "").trim();
        if (!rawDate) {
          upcomingItems.push(item);
          continue;
        }
        const parsed = new Date(`${rawDate}T00:00:00`);
        if (Number.isNaN(parsed.getTime()) || parsed > today) {
          upcomingItems.push(item);
        } else {
          releasedItems.push(item);
        }
      }
      sortByDateDesc(releasedItems);
      sortByDateAsc(upcomingItems);
    }

    renderPosters(elements.gameReleaseGrid, releasedItems, "No new game releases found.");
    renderPosters(elements.gameComingSoonGrid, upcomingItems, "No upcoming games found.");
  } catch (error) {
    elements.gameReleaseGrid.innerHTML = `<p class="empty">${error.message}</p>`;
    elements.gameComingSoonGrid.innerHTML = `<p class="empty">${error.message}</p>`;
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
    renderEventCategoryFilters();
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

async function loadBandsintownEvents() {
  if (!elements.bandsintownEventsList) {
    return;
  }
  try {
    const [eventsResponse, configResponse] = await Promise.all([
      fetch(BANDSINTOWN_EVENTS_PATH, { cache: "no-store" }),
      fetch(BANDSINTOWN_GENRE_FILTERS_PATH, { cache: "no-store" }),
    ]);
    if (!eventsResponse.ok) {
      throw new Error(`Could not load ${BANDSINTOWN_EVENTS_PATH}`);
    }
    const events = await eventsResponse.json();
    let configuredGenres = [];
    if (configResponse.ok) {
      const config = await configResponse.json();
      configuredGenres = Array.isArray(config?.genres)
        ? unique(config.genres.map((genre) => String(genre || "").trim()).filter(Boolean))
        : [];
    }
    state.bandsintownGenreFilters = configuredGenres;
    state.bandsintownEvents = Array.isArray(events) ? events : [];
    renderBandsintownEvents(state.bandsintownEvents);
  } catch (error) {
    state.bandsintownGenreFilters = [];
    state.bandsintownEvents = [];
    elements.bandsintownEventsList.innerHTML = `<p class="empty">${error.message}</p>`;
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

if (elements.watchlistOpinionIndicatorsToggle) {
  elements.watchlistOpinionIndicatorsToggle.checked = state.showOpinionIndicators;
  elements.watchlistOpinionIndicatorsToggle.addEventListener("click", (event) => {
    event.stopPropagation();
  });
  elements.watchlistOpinionIndicatorsToggle.addEventListener("change", (event) => {
    state.showOpinionIndicators = Boolean(event.target.checked);
    renderWatchlistAll();
  });
}

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

if (elements.layoutEditToggle) {
  elements.layoutEditToggle.addEventListener("click", () => {
    const isEditing = !document.body.classList.contains("is-editing-layout");
    setLayoutEditMode(isEditing);
  });
}

if (elements.watchlistMediaButtons) {
  elements.watchlistMediaButtons.addEventListener("click", (event) => {
    const button = event.target.closest(".watchlist-media-button");
    if (!button) {
      return;
    }
    const media = button.dataset.watchMedia || "screen";
    setWatchlistMedia(media);
    renderWatchlistAll();
  });
}

if (elements.watchlistCategoryButtons) {
  elements.watchlistCategoryButtons.addEventListener("click", (event) => {
    const button = event.target.closest(".watchlist-category-button");
    if (!button) {
      return;
    }
    const type = button.dataset.watchType || "";
    if (!type) {
      return;
    }
    toggleWatchlistType(type);
    renderWatchlistAll();
  });
}

if (elements.watchlistYearFilter) {
  elements.watchlistYearFilter.addEventListener("change", (event) => {
    state.watchlistYearFilter = event.target.value || "all";
    renderWatchlistAll();
  });
}

if (elements.watchlistCollectionFilter) {
  elements.watchlistCollectionFilter.addEventListener("change", (event) => {
    state.watchlistCollectionFilter = event.target.value || "watched";
    state.watchlistYearFilter = "all";
    renderWatchlistAll();
  });
}

if (elements.watchlistSearchFilter) {
  elements.watchlistSearchFilter.addEventListener("input", (event) => {
    state.watchlistSearchFilter = String(event.target.value || "");
    renderWatchlistAll();
  });
}

if (elements.watchlistGenreFilter) {
  elements.watchlistGenreFilter.addEventListener("change", (event) => {
    state.watchlistGenreFilter = event.target.value || "all";
    renderWatchlistAll();
  });
}

if (elements.watchlistSort) {
  elements.watchlistSort.addEventListener("change", (event) => {
    state.watchlistSort = event.target.value || "default";
    renderWatchlistAll();
  });
}

if (elements.watchlistOpinionFilter) {
  elements.watchlistOpinionFilter.addEventListener("change", (event) => {
    state.watchlistOpinionFilter = event.target.value || "all";
    renderWatchlistAll();
  });
}

for (const container of [elements.watchlistCurrent, elements.watchlistHistory]) {
  if (!container) {
    continue;
  }
  container.addEventListener("click", (event) => {
    const button = event.target.closest(".watchlist-entry-button");
    if (!button) {
      return;
    }
    const type = button.dataset.watchType || "movie";
    const encodedTitle = button.dataset.watchTitle || "";
    const title = decodeURIComponent(encodedTitle);
    if (!title) {
      return;
    }
    openWatchlistDetail(type, title);
  });
}

if (elements.newsList) {
  elements.newsList.addEventListener("click", (event) => {
    const card = event.target.closest(".news-card");
    if (!card) {
      return;
    }
    state.selectedNewsId = card.dataset.newsId || "";
    renderNews(state.newsItems);
  });
}

if (elements.releaseGrid) {
  elements.releaseGrid.addEventListener("click", (event) => {
    const card = event.target.closest(".poster-card[data-release-index]");
    if (!card) {
      return;
    }
    event.preventDefault();
    const index = Number(card.dataset.releaseIndex);
    if (!Number.isInteger(index) || index < 0 || index >= state.releaseItems.length) {
      return;
    }
    openReleaseDetail(state.releaseItems[index]);
  });
}

if (elements.bandsintownEventsList) {
  elements.bandsintownEventsList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-bandsintown-genre]");
    if (!button) {
      return;
    }
    event.preventDefault();
    const next = button.dataset.bandsintownGenre || "all";
    state.selectedBandsintownGenre = next;
    renderBandsintownEvents(state.bandsintownEvents);
  });
}

if (elements.newsCategoryButtons) {
  elements.newsCategoryButtons.addEventListener("click", (event) => {
    const button = event.target.closest("[data-news-category]");
    if (!button) {
      return;
    }
    state.selectedNewsCategory = button.dataset.newsCategory || "all";
    state.selectedNewsId = "";
    renderNews(state.newsAllItems);
  });
}

if (elements.newsExpandToggle && elements.newsList) {
  elements.newsExpandToggle.addEventListener("click", () => {
    state.isNewsExpanded = !state.isNewsExpanded;
    elements.newsList.classList.toggle("is-expanded", state.isNewsExpanded);
    elements.newsExpandToggle.textContent = state.isNewsExpanded ? "Retract" : "Expand";
  });
}

if (elements.watchlistDetailClose && elements.watchlistDetailPanel) {
  elements.watchlistDetailClose.addEventListener("click", () => {
    elements.watchlistDetailPanel.hidden = true;
    elements.watchlistDetailPanel.classList.remove("is-open");
    elements.watchlistDetailPanel.classList.remove("is-loved");
    elements.watchlistDetailPanel.classList.remove(
      "opinion-loved",
      "opinion-liked",
      "opinion-mixed",
      "opinion-disliked",
      "opinion-hated",
    );
    elements.watchlistDetailPanel.dataset.watchOpinion = "";
    document.body.classList.remove("watchlist-detail-open");
  });
}

const storedTheme = loadThemePreference();
if (storedTheme) {
  applyTheme(storedTheme);
} else {
  applyTheme("light");
}

setupDashboardSectionEditor();

load();
setHeaderDate();
loadMetadata();
loadWeather();
loadReleases();
loadComingSoon();
loadGameReleases();
loadNews();
loadWatchlist();
loadSpecials();
loadBandsintownEvents();
loadQuicketEvents();
syncRangeButtons();
