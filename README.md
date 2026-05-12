# My Dashboard

Local dashboard plus scraper services for media, news, One Piece cards, release radar, and events/specials.

## Dashboard

Serve the dashboard from the repo root:

```powershell
python -m http.server 8080
```

Open:

```text
http://localhost:8080/docs/
```

Dashboard files live in:

- `docs/index.html`
- `docs/app.js`
- `docs/styles.css`

Runtime data lives in `data/`. The dashboard copy lives in `docs/data/` and is refreshed by the wrapper scripts.

## Data Shape

Each dashboard module has data under `data/<module>/`, service code under `services/<module>/`, and module config in `data/<module>/config.json`.

Events, specials, and places are linked like this:

- `data/events/places.json`: Cape Town places by name. A place has `name`, `address`, `location_key`, `type`, `tags`, map URLs, and `missing_location`. It does not store `lat` or `lng`.
- `data/events/locations.json`: address/location strings mapped to coordinates.
- `data/events/specials.json`: specials grouped by day. Each special links to a place with `place` and `place_key`; if no place exists it has `missing_place`.
- Event source JSON files: events can link to a place with `place_key` or to an address with `location_key`. If neither can be resolved, the dashboard shows the corner `X`.

## Scraping

Use the module-level wrappers in `services/` for normal scraping. All wrappers accept:

- `--hard`: recreate selected generated data from scratch where applicable.
- `--skip-geocode`: for `scrape_events.py`, skip the final geocode pass.
- `--source`: scrape one source instead of all sources in that module.
- `--limit`: max items per supported source. `0` means no limit where supported.
- `--max-pages`: max listing pages per supported source. `0` means source default/all.

### Events

Run all event sources:

```powershell
python services/scrape_events.py
python services/scrape_events.py --skip-geocode
```

This runs in two phases:
- Scrape sources (specials, places, Bandsintown, Quicket, Webtickets, Google Calendar).
- Final geocode pass across all event/place `location_key` values, updating `locations.json` incrementally after each hit.

Run one source hard with a test limit:

```powershell
python services/scrape_events.py --source bandsintown --hard --limit 10 --max-pages 10
```

Allowed sources:

- `all`
- `specials`
- `bandsintown`
- `quicket`
- `webtickets`
- `google-calendar`

Standalone geocode pass:

```powershell
python services/events/geocode_event_locations.py
python services/events/geocode_event_locations.py --hard
```

Extra Bandsintown option:

```powershell
python services/scrape_events.py --source bandsintown --genre metal --limit 10
python services/scrape_events.py --source bandsintown --genre all --limit 10
```

Individual event source scripts:

```powershell
python services/events/scrape_specials.py --hard
python services/events/scrape_bandsintown_events.py --hard --genre metal --limit 10 --max-pages 10
python services/events/scrape_quicket_events.py --hard --limit 10 --pages 10 --days 365
python services/events/scrape_webtickets_events.py --hard --limit 10 --max-pages 10
python services/events/scrape_google_calendar.py --hard
```

Events config:

- `data/events/config.json`
- `docs/data/events/config.json`

Bandsintown dashboard genre buttons are configured at `bandsintown.genre_filters`.

### Media

Run media/watchlist scraping:

```powershell
python services/scrape_media.py
```

Examples:

```powershell
python services/scrape_media.py --hard
python services/scrape_media.py --source watchlist --type movies
python services/scrape_media.py --source games --type games --hard
```

Allowed sources:

- `all`
- `watchlist`
- `games`

Allowed types:

- `all`
- `movies`
- `series`
- `anime`
- `games`

Individual source script:

```powershell
python services/media/scrape_watchlist.py --scope both --type all --hard
```

Media config:

- `data/media/config.json`

### One Piece

Run all One Piece store scrapes:

```powershell
python services/scrape_one_piece.py
```

Examples:

```powershell
python services/scrape_one_piece.py --source tanuki
python services/scrape_one_piece.py --source all --hard
```

Allowed sources:

- `all`
- `bigbang`
- `knightly`
- `marvellous`
- `tanuki`

Individual source script:

```powershell
python services/one_piece/find_missing_cards.py all
python services/one_piece/find_missing_cards.py tanuki
```

One Piece config:

- `data/one_piece/config.json`

### Release Radar

Run all release radar sources:

```powershell
python services/scrape_release_radar.py
```

Examples:

```powershell
python services/scrape_release_radar.py --source pahe --hard --limit 10
python services/scrape_release_radar.py --source coming-soon --limit 10 --max-pages 3
python services/scrape_release_radar.py --source games --limit 10 --max-pages 3
```

Allowed sources:

- `all`
- `pahe`
- `coming-soon`
- `games`

Individual source scripts:

```powershell
python services/release_radar/scrape_releases.py
python services/release_radar/scrape_coming_soon.py
python services/release_radar/scrape_game_releases.py
```

Release radar config:

- `data/release_radar/config.json`

### News

News pulls curated RSS/Atom feeds for global, South African, games, entertainment, and climbing headlines.

```powershell
python services/scrape_news.py
python services/scrape_news.py --limit 6
python services/scrape_news.py --source local-file
```

Allowed sources:

- `all`
- `rss`
- `local-file`

News config:

- `data/news/config.json`

Important/breaking filtering:

- Dashboard now prefers `top_items` from `data/news/news.json` when available.
- Tune `importance_threshold`, `breaking_threshold`, `max_top_items_per_category`, and `category_max_age_hours` in `data/news/config.json`.

News scraping sources by topic:

- `Global`: BBC World, Al Jazeera, The Guardian World
- `South Africa`: GroundUp, IOL South Africa
- `Cape Town`: Cape Town ETC, IOL Cape Times
- `Cape Town Events`: What’s On in Cape Town (events feed), Events in Cape Town (feed), and Wesgro Travel Events (scraped from event listings)
- `Games`: GameSpot, PC Gamer, PlayStation Blog
- `F1`: BBC Sport F1, Motorsport.com F1
- `F1 Snapshot`: auto-generated pinned module with current Driver/Constructor standings, race schedule, completed race results, and race highlights. Structured standings/results come from Jolpica/Ergast; race highlights are matched from Wikipedia race summaries plus F1 race-report feeds from Autosport, RaceFans, RACER, and Motorsport.com.
- `Entertainment`: Variety, The Hollywood Reporter, Deadline
- `Climbing`: Gripped, GearJunkie Climbing, Alpinist

## Local Full Update

The older local update runner still works and now calls the module wrappers:

```powershell
python run_local_dashboard_update.py all
python run_local_dashboard_update.py events
python run_local_dashboard_update.py media
python run_local_dashboard_update.py cards
python run_local_dashboard_update.py releases
python run_local_dashboard_update.py news
```

## Secrets

Secrets are read from environment variables, `secrets.env`, or `env.py` helpers depending on the scraper. Start from:

```text
secrets.env.example
```
