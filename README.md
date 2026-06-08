# Weather

Flask weather dashboard using QWeather APIs. The app renders a Chinese weather UI with current conditions, a 24-hour forecast, a 7-day forecast, air quality, life indices, browser geolocation, and GeoAPI city search.

## Tech Stack

- Python 3 + Flask
- QWeather GeoAPI, Weather API, Indices API, and Air Quality API
- Ed25519 JWT authentication via `cryptography`
- Vanilla HTML/CSS/JavaScript

## Project Layout

```text
weather_app/__init__.py   Flask app factory and package entrypoint
weather_app/config.py     Paths, QWeather constants, icon maps, and in-memory caches
weather_app/qweather.py   QWeather auth, GeoAPI lookup, API requests, cache, and fallback loading
weather_app/view_models.py
                          Dashboard data shaping from QWeather payloads
weather_app/formatting.py Number and date/time formatting helpers
weather_app/icons.py      QWeather icon and background theme mapping
weather_app/routes.py     Page route and JSON API endpoints
templates/index.html      Main Jinja template
static/css/style.css      UI styling and responsive layout
static/js/app.js          ES module bootstrap
static/js/modules/        Frontend modules for API calls, city search, geolocation,
                          refresh handling, modal behavior, navigation, and storage
data/qweather_sample.json Local fallback sample payload
requirements.txt          Python dependencies
.env.example              Local QWeather configuration template
```

## Configuration

Create a private `.env` file from `.env.example` and fill in the QWeather values:

```text
QWEATHER_API_HOST=https://your-subdomain.qweatherapi.com
QWEATHER_KEY_ID=your-key-id
QWEATHER_PROJECT_ID=your-project-id
QWEATHER_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----..."
```

Do not commit `.env`; it is ignored by Git.

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app "weather_app:create_app" run --host 127.0.0.1 --port 5000 --no-reload
```

Open:

```text
http://127.0.0.1:5000/
```

## Routes

- `GET /` renders the dashboard.
- `GET /api/weather?location=<qweather-location-id>` refreshes weather metadata for the selected location.
- `GET /api/cities?q=<query>` searches QWeather GeoAPI cities. It accepts city names and longitude/latitude queries.

## Behavior Notes

- Default location is QWeather location `101240704` (南康).
- Browser geolocation is attempted on first load when no `location` query parameter is present.
- If geolocation succeeds, the app resolves the coordinates through GeoAPI and navigates to `?location=<id>`.
- If geolocation is unavailable, the frontend falls back to the last selected location, then the backend default.
- Successful weather API payloads are cached for 60 seconds per location.
- City search results are cached for 60 seconds per query.
- Weather API fetch retries up to 3 times; failed calls do not overwrite a successful cache entry.

## Development Checks

```powershell
.\.venv\Scripts\python.exe -m compileall weather_app
$node = "C:\Users\JinxiHexi\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
Get-ChildItem static\js -Recurse -Filter *.js | ForEach-Object { & $node --check $_.FullName }
```
