# ClimateScope — Environmental Stressor Observatory

ClimateScope is a climate-hazard analysis platform designed to help explore historical environmental patterns and identify periods of elevated climate risk.

**Heatwaves are the first hazard module.** The initial implementation analyzes historical daily maximum temperatures, classifies heatwave events against a climatological baseline, and presents annual trends and event-level results through an interactive dashboard.

## Highlights

- **Historical weather data:** Uses the Open-Meteo Historical Weather API with the ERA5-Land model.
- **Climatological baseline:** Uses the 1991–2020 reference period.
- **Heatwave detection:** Identifies multi-day periods that meet percentile-based temperature thresholds.
- **Severity classification:** Supports moderate and extreme heatwave classifications.
- **Trend analysis:** Aggregates annual heatwave metrics, estimates Theil–Sen slope, and provides LOWESS smoothing for visualization.
- **Interactive dashboard:** Explore analysis results, events, trends, and methodology.
- **Export:** Download analysis results as CSV and PDF.
- **Data-quality handling:** Handles missing or invalid observations according to the configured cleaning rules.
- **Automated tests:** Includes tests for baseline generation, data quality, heatwave classification, analysis workflows, API behavior, caching, and trends.

## Technology stack

| Area | Technology |
|---|---|
| Frontend | React, Vite, Material UI, Recharts |
| Maps | Leaflet |
| Date handling | Day.js / MUI X Date Pickers |
| Backend | Python, FastAPI |
| Weather data | Open-Meteo Historical Weather API, ERA5-Land |
| Database / baseline cache | MongoDB Atlas |
| Analysis | Pandas, NumPy, Statsmodels |
| Testing | Pytest |

> Confirm the final dependency list against the project's `package.json` and `requirements.txt` before publishing this README.

## How it works

1. **Select a location and analysis period.** The dashboard accepts a supported location and date range.
2. **Retrieve historical weather data.** The backend obtains daily maximum-temperature observations from Open-Meteo using ERA5-Land.
3. **Validate and clean observations.** Invalid values and missing data are handled using the project's data-quality rules.
4. **Compare temperatures with the baseline.** Daily temperatures are evaluated against day-of-year climatological percentile thresholds calculated from 1991–2020.
5. **Detect heatwave events.** Consecutive days meeting the configured percentile criteria are grouped into events.
6. **Summarize and visualize results.** The API returns event and annual trend information for the dashboard.

## Heatwave methodology

The baseline is calculated from **1 January 1991 through 31 December 2020** using ERA5-Land data.

The current methodology configuration includes:

- Baseline period: `1991-01-01` to `2020-12-31`
- Climatological window: 5 days
- Percentile thresholds: 90th and 95th percentiles
- Minimum baseline observations: 100
- Leap-day handling: 29 February thresholds are derived by averaging the 28 February and 1 March thresholds
- Missing-data handling: short gaps may be interpolated according to the configured maximum gap; longer gaps are treated as insufficient data

The heatwave classification currently uses multi-day events:

- **Moderate:** At least 3 consecutive days meeting or exceeding the 90th-percentile threshold
- **Extreme:** At least 3 consecutive days meeting or exceeding the 95th-percentile threshold

Consult the methodology view and implementation for the precise rules used to assign event severity and calculate metrics.

### Trend interpretation

Annual summaries include heatwave metrics and a Theil–Sen slope estimate for the annual total of heatwave days. The slope is reported per decade. LOWESS smoothing is provided to help visualize the shape of the trend.

**Important limitations:**

- LOWESS is a descriptive smoothing method, not evidence of a statistically significant trend.
- The current trend analysis does not establish statistical significance or causation.
- Event-attributed heatwave days are assigned to an event's start year. For events spanning calendar years, this differs from counting each event day in its actual calendar year.
- Results depend on data availability, baseline coverage, quality-control decisions, and the chosen thresholds.

## Project structure

The following is a suggested layout for a single repository containing the frontend and backend. Adjust directory names to match the actual repository:

```text
climatescope/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   └── services/
│   ├── tests/
│   ├── requirements.txt
│   └── pytest.ini
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── ...
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.12 recommended for the current backend environment
- Node.js compatible with the frontend toolchain (Node.js 22 was used during development)
- npm
- A MongoDB Atlas deployment if using the configured persistent baseline cache
- Internet access for Open-Meteo data retrieval

## Local setup

Run commands from the relevant backend or frontend directory. The examples below assume the suggested `backend/` and `frontend/` layout.

### 1. Backend

```bash
cd backend

python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Configure the backend's required environment variables using the names expected by the application. Do not commit credentials.

If the application requires MongoDB, configure its connection URI and database settings before starting the API. Use an environment file locally if supported by the application, and keep it out of version control.

Start the development server:

```bash
uvicorn app.main:app --reload
```

The API should be available at:

- API base URL: `http://127.0.0.1:8000`
- Interactive API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

The primary heatwave trend endpoint is:

```text
GET /api/v1/heatwaves/trends
```

Check the API documentation for the exact required query parameters and response schema.

### 2. Frontend

In a separate terminal:

```bash
cd frontend
npm install
```

Create a local environment file such as `.env.local` if the frontend uses Vite environment variables:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Start the development server:

```bash
npm run dev
```

Use the local URL printed by Vite in the terminal.

For production, set `VITE_API_BASE_URL` to the deployed backend URL **before building** the frontend.

## Running tests

Run backend tests from the backend directory with the virtual environment activated:

```bash
pytest
```

Run a specific test module:

```bash
pytest tests/test_baseline.py
pytest tests/test_data_quality.py
pytest tests/test_heatwave.py
pytest tests/test_heatwave_analysis.py
pytest tests/test_trends.py
pytest tests/test_api.py
pytest tests/test_baseline_cache.py
```

The test suite covers baseline calculations, data-quality rules, heatwave classification and analysis, API behavior, trend calculations, and cache behavior.

Tests that mock external services should not require live service credentials. Separately verify real MongoDB Atlas connectivity when validating the environment or deployment.

**Development verification:** The full backend test suite passed with **63 tests** in the latest recorded run. The frontend production build also succeeded. These are development-time results, not a guarantee that a future checkout or deployment will pass without re-running the checks.

## Production build

Build the frontend:

```bash
cd frontend
npm run build
```

Vite writes the production output to `dist/` by default. Deploy the generated assets using your chosen frontend host.

## Deployment outline

A simple deployment setup is:

- **Frontend:** Vercel or another static frontend host
- **Backend:** Render or another host that supports Python/FastAPI
- **Database/cache:** MongoDB Atlas, if required by the configured application

Before deploying:

1. Set the production `VITE_API_BASE_URL` to the public backend URL and rebuild the frontend.
2. Configure backend CORS to allow the exact deployed frontend origin.
3. Set database credentials and other secrets as server-side environment variables.
4. Confirm the backend can connect to MongoDB Atlas from the hosting environment.
5. Verify `/health`, the API documentation, and the heatwave endpoint.
6. Test the deployed dashboard with a representative location and date range.

Never put database credentials, API secrets, or private connection strings in frontend environment variables or commit them to Git.

## Data sources and attribution

- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [Open-Meteo](https://open-meteo.com/)

Review the applicable Open-Meteo terms and attribution requirements before public or commercial deployment.

## Known limitations and future work

- Heatwaves are the first hazard type; the broader platform is intended to accommodate additional environmental stressors.
- Trend estimates are descriptive and do not currently provide a statistical significance test.
- Baseline availability and quality depend on the underlying historical data and the configured minimum-observation rules.
- Large frontend dependencies, including export libraries, may increase the initial JavaScript bundle size; code-splitting can be considered as the dashboard grows.
- Production behavior should be validated against the deployed API, database, CORS configuration, and real data requests.

## Development principles

- Keep baseline and event-classification rules testable and versioned.
- Separate data cleaning, baseline computation, hazard detection, trend analysis, and API presentation.
- Preserve tests for important edge cases and data-quality behavior.
- Document methodology changes so users can interpret results consistently.

## License

No license has been specified yet. Add a `LICENSE` file and update this section before inviting reuse or external contributions.
