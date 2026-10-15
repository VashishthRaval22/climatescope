
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Skeleton,
  IconButton,
  Tooltip,
  Divider,
  Container,
  CssBaseline,
  Paper,
  Stack,
  Tabs,
  Tab,
  TextField,
  ThemeProvider,
  Typography,
  createTheme,
} from '@mui/material';
import {
  Thermostat,
  Whatshot,
  CalendarMonth,
  TrendingUp,
  Search,
  LocationOn,
  PictureAsPdf,
  TableView,
  MapOutlined,
} from '@mui/icons-material';
import {
  CartesianGrid,
  Bar,
  BarChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  Legend,
  XAxis,
  YAxis,
} from 'recharts';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs from 'dayjs';
import { MapContainer, TileLayer, Marker, useMapEvents, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './App.css';

import AnalysisSettings from './components/AnalysisSettings.jsx';
import { MetricCard, SectionHeading, PaginationBar, SkeletonDashboard, AnimatedWords } from './components/DashboardPrimitives.jsx';
import { downloadCsv, exportPdf } from './utils/exportUtils.js';
import { getYearTicks } from './utils/chartUtils.js';


const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '');

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#c2410c' },
    background: { default: '#f7f8fa', paper: '#ffffff' },
    text: { primary: '#172033', secondary: '#667085' },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h4: { fontWeight: 750, letterSpacing: '-1px' },
    h6: { fontWeight: 700 },
  },
  shape: { borderRadius: 14 },
});

async function fetchJson(url) {
  const response = await fetch(url);
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = body.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join(', ')
      : typeof detail === 'string'
        ? detail
        : `Request failed (${response.status})`;

    throw new Error(message);
  }

  return body;
}

function formatDate(value) {
  if (!value) return '—';

  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${value}T00:00:00Z`));
}

function isValidDateInput(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function App() {
  const [latitude, setLatitude] = useState('19.076');
  const [longitude, setLongitude] = useState('72.8777');
  const [cityQuery, setCityQuery] = useState('Mumbai, Maharashtra, India');
  const [cityOptions, setCityOptions] = useState([]);
  const [cityLoading, setCityLoading] = useState(false);
  const [startDate, setStartDate] = useState('1991-01-01');
  const [endDate, setEndDate] = useState('2020-12-31');
  const [appliedFilters, setAppliedFilters] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [showMap, setShowMap] = useState(false);
  const [trendPage, setTrendPage] = useState(0);
  const [eventsPage, setEventsPage] = useState(0);
  const rowsPerPage = 10;
  const requestIdRef = useRef(0);

  const [trends, setTrends] = useState([]);
  const [trendAnalysis, setTrendAnalysis] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);

  const selectedStartYear = appliedFilters ? Number(appliedFilters.startDate.slice(0, 4)) : null;
  const selectedEndYear = appliedFilters ? Number(appliedFilters.endDate.slice(0, 4)) : null;

  const loadDashboard = useCallback(async () => {
    const lat = Number(latitude);
    const lon = Number(longitude);
    const firstYear = Number(startDate.slice(0, 4));
    const lastYear = Number(endDate.slice(0, 4));

    if (
      !latitude.trim() ||
      !longitude.trim() ||
      !startDate.trim() ||
      !endDate.trim() ||
      !Number.isFinite(lat) ||
      !Number.isFinite(lon) ||
      lat < -90 ||
      lat > 90 ||
      lon < -180 ||
      lon > 180
    ) {
      setError('Enter valid latitude and longitude values.');
      return;
    }

    if (
      !isValidDateInput(startDate) ||
      !isValidDateInput(endDate) ||
      startDate < '1950-01-01' ||
      endDate > '2025-12-31' ||
      startDate > endDate
    ) {
      setError('Choose a valid date range between 1950 and 2025.');
      return;
    }

    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError('');

    const trendsParams = new URLSearchParams({
      latitude: String(lat),
      longitude: String(lon),
      start_year: String(firstYear),
      end_year: String(lastYear),
    });

    const analysisParams = new URLSearchParams({
      latitude: String(lat),
      longitude: String(lon),
      start_date: startDate,
      end_date: endDate,
    });

    try {
      const [trendsResult, analysisResult] = await Promise.all([
        fetchJson(
          `${API_BASE_URL}/api/v1/heatwaves/trends?${trendsParams.toString()}`,
        ),
        fetchJson(
          `${API_BASE_URL}/api/v1/heatwaves?${analysisParams.toString()}`,
        ),
      ]);

      if (requestId !== requestIdRef.current) return;
      setTrends(trendsResult.trends ?? []);
      setTrendAnalysis(trendsResult.trend_analysis ?? null);
      setAnalysis(analysisResult);
      setAppliedFilters({
        latitude: String(lat),
        longitude: String(lon),
        startDate,
        endDate,
        location: cityQuery.trim() || `${lat.toFixed(3)}, ${lon.toFixed(3)}`,
      });
      setLastUpdated(new Date());
      setActiveTab('overview');
      setTrendPage(0);
      setEventsPage(0);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setError(
        err instanceof TypeError
          ? 'Could not reach the API. Check that FastAPI is running and CORS is configured.'
          : err.message || 'Unable to load climate data.',
      );
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [latitude, longitude, startDate, endDate, cityQuery]);

  // Open-Meteo geocoding autocomplete. Debouncing and cancellation keep this
  // lightweight while the user types.
  useEffect(() => {
    const query = cityQuery.trim();
    if (query.length < 2 || query === 'Mumbai, Maharashtra, India') {
      setCityOptions([]);
      setCityLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    const timeoutId = window.setTimeout(async () => {
      setCityLoading(true);
      try {
        const params = new URLSearchParams({
          name: query,
          count: '8',
          language: 'en',
          format: 'json',
        });
        const response = await fetch(
          `https://geocoding-api.open-meteo.com/v1/search?${params.toString()}`,
          { signal: controller.signal },
        );
        if (!response.ok) throw new Error('City search is temporarily unavailable.');
        const body = await response.json();
        setCityOptions(
          (body.results ?? []).map((place) => ({
            ...place,
            label: [place.name, place.admin1, place.country].filter(Boolean).filter((value, index, values) => values.indexOf(value) === index).join(', '),
          })),
        );
      } catch (err) {
        if (err.name !== 'AbortError') setCityOptions([]);
      } finally {
        if (!controller.signal.aborted) setCityLoading(false);
      }
    }, 300);

    return () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [cityQuery]);

  const summary = analysis?.summary ?? {};
  const trendHeadline = trendAnalysis?.headline;
  const trendSlope = trendHeadline?.slope_per_decade;
  const trendSlopeLabel = Number.isFinite(trendSlope)
    ? `${trendSlope > 0 ? '+' : ''}${Number(trendSlope).toFixed(1)} days / decade`
    : '—';
  const events = analysis?.events ?? [];
  const quality = analysis?.data_quality?.analysis_period;
  const paginatedTrends = trends.slice(trendPage * rowsPerPage, (trendPage + 1) * rowsPerPage);
  const paginatedEvents = events.slice(eventsPage * rowsPerPage, (eventsPage + 1) * rowsPerPage);
  const filtersDirty = !appliedFilters ||
    String(latitude) !== appliedFilters.latitude ||
    String(longitude) !== appliedFilters.longitude ||
    startDate !== appliedFilters.startDate || endDate !== appliedFilters.endDate ||
    (cityQuery.trim() || `${Number(latitude).toFixed(3)}, ${Number(longitude).toFixed(3)}`) !== appliedFilters.location;
  const eventHeaders = ['Start date', 'End date', 'Duration (days)', 'Peak temperature (C)', 'Mean temperature (C)', 'Classification', 'Imputed days'];
  const eventRows = events.map((event) => [event.start_date, event.end_date, event.duration_days, event.peak_temperature_c, event.mean_temperature_c, event.is_extreme ? 'Extreme' : 'Moderate', event.imputed_days ?? 0]);
  const trendHeaders = ['Year', 'Events', 'Extreme events', 'Heatwave days', 'Longest event (days)', 'Peak temperature (C)'];
  const trendRows = trends.map((item) => [item.year, item.heatwave_events, item.extreme_heatwave_events, item.total_heatwave_days, item.longest_heatwave_days, item.peak_temperature_c]);
  const exportSubtitle = `${appliedFilters?.location ?? ''} · ${appliedFilters?.startDate ?? ''} to ${appliedFilters?.endDate ?? ''} · ${Number(appliedFilters?.latitude).toFixed(4)}, ${Number(appliedFilters?.longitude).toFixed(4)}`;
  const chooseMapPoint = (lat, lon) => {
    setLatitude(lat.toFixed(5)); setLongitude(lon.toFixed(5));
    setCityQuery(`Map selection (${lat.toFixed(3)}, ${lon.toFixed(3)})`);
  };


  const peakTemperature = useMemo(() => {
    const peaks = events
      .map((event) => event.peak_temperature_c)
      .filter((value) => Number.isFinite(value));

    return peaks.length ? Math.max(...peaks) : null;
  }, [events]);

  const chartTooltipStyle = {
    borderRadius: 10,
    border: '1px solid #e5e7eb',
    boxShadow: '0 8px 24px rgba(15, 23, 42, 0.08)',
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale="en-gb">
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box className="app-shell">
        <Box className="topbar">
          <Container maxWidth="xl" className="topbar-inner">
            <Box className="brand">
              <Box className="brand-mark">
                <Whatshot />
              </Box>
              <Box>
                <Typography className="brand-name">
                  ClimateScope
                </Typography>
                <Typography className="brand-subtitle">
                  Climate hazard intelligence
                </Typography>
              </Box>
            </Box>
            <Chip
              size="small"
              label="Historical analysis"
              className="header-chip"
            />
          </Container>
        </Box>

        <Container maxWidth="xl" className="dashboard-container">
          <Box className="page-intro">
            <Box>
              <Typography className="eyebrow">
                CLIMATE HAZARD INTELLIGENCE / HEATWAVES
              </Typography>
              <Typography variant="h4" className="page-title">
                Environmental Stressor Observatory
              </Typography>
              <Typography color="text.secondary" className="page-description">
                Evaluate regional climate shift trajectories and extreme events through high-resolution historical reanalysis.
              </Typography>
            </Box>
          </Box>

          <AnalysisSettings
            latitude={latitude}
            setLatitude={setLatitude}
            longitude={longitude}
            setLongitude={setLongitude}
            cityQuery={cityQuery}
            setCityQuery={setCityQuery}
            cityOptions={cityOptions}
            cityLoading={cityLoading}
            startDate={startDate}
            setStartDate={setStartDate}
            endDate={endDate}
            setEndDate={setEndDate}
            loading={loading}
            analysis={analysis}
            filtersDirty={filtersDirty}
            loadDashboard={loadDashboard}
            showMap={showMap}
            setShowMap={setShowMap}
            chooseMapPoint={chooseMapPoint}
          />

          {error && (
            <Alert
              severity="error"
              className="status-alert"
              action={
                <Button color="inherit" size="small" onClick={loadDashboard}>
                  Retry
                </Button>
              }
            >
              {error}
            </Alert>
          )}

          {loading && <>
            <Paper className="loading-panel loading-banner" elevation={0}>
              <CircularProgress size={20} />
              <Box sx={{ flex: 1 }}>
                <Typography fontWeight={700}>{analysis ? 'Refreshing climate analysis…' : 'Analyzing localized thermal anomalies…'}</Typography>
                <AnimatedWords text="Computing daily maximum temperatures against the 1991-2020 ERA5-Land baseline matrix. Dropping leap-day noise." />
              </Box>
            </Paper>
            <SkeletonDashboard />
          </>}

          {!error && !loading && !analysis && (
            <Paper className="welcome-panel" elevation={0}>
              <Box className="welcome-copy">
                <Typography className="eyebrow">CLIMATE HORIZON TRACKING</Typography>
                <Typography variant="h4" className="welcome-title">Decode regional vulnerability over time.</Typography>
                <Typography color="text.secondary" className="page-description">
                  ClimateScope surfaces shifting baseline anomalies, benchmarks historical multi-hazard events, and monitors spatial vulnerability with rigorous data-quality validation. Heatwaves are our first hazard module.
                </Typography>
                <Button variant="contained" startIcon={<Search />} onClick={loadDashboard} disabled={loading} sx={{ mt: 2, alignSelf: 'flex-start' }}>
                  Run first analysis
                </Button>
              </Box>
              <Box className="welcome-facts">
                <Box><Typography variant="h6">ERA5-Land</Typography><Typography variant="body2" color="text.secondary">Historical temperature data</Typography></Box>
                <Box><Typography variant="h6">1991-2020</Typography><Typography variant="body2" color="text.secondary">Reference climatology</Typography></Box>
                <Box><Typography variant="h6">P90 / P95</Typography><Typography variant="body2" color="text.secondary">Moderate and extreme thresholds</Typography></Box>
              </Box>
            </Paper>
          )}

          {!error && !loading && analysis && (
            <>
              <Tabs className="dashboard-tabs" value={activeTab} onChange={(_, value) => setActiveTab(value)} aria-label="Analysis views" variant="scrollable" scrollButtons="auto">
                <Tab value="overview" label="Overview" />
                <Tab value="events" label="Hazard Incidents" />
                <Tab value="methodology" label="Data & methodology" />
              </Tabs>
              {activeTab === 'overview' && <>
              <Box className="overview-heading">
                <Box>
                  <Typography variant="h6">
                    {appliedFilters.location} · {appliedFilters.startDate} to {appliedFilters.endDate}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {Number(appliedFilters.latitude).toFixed(3)}, {Number(appliedFilters.longitude).toFixed(3)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Heatwave summary for the selected date range. Trend charts show annual comparisons for the calendar years covered.
                  </Typography>
                </Box>
                <Chip
                  icon={<CalendarMonth />}
                  label={`${selectedStartYear} – ${selectedEndYear} annual trends`}
                  variant="outlined"
                />
              </Box>

              <Box className="metrics-grid">
                <MetricCard
                  icon={<Whatshot />}
                  label="Hazard Incidents"
                  value={summary.total_heatwave_events ?? 0}
                  helper="Within selected date range"
                />
                <MetricCard
                  icon={<TrendingUp />}
                  label="Severe Spikes"
                  value={summary.extreme_heatwave_events ?? 0}
                  helper="Events meeting the extreme threshold"
                />
                <MetricCard
                  icon={<CalendarMonth />}
                  label="Active Hazard Days"
                  value={summary.total_heatwave_days ?? 0}
                  helper="Total days across detected events"
                />
                <MetricCard
                  icon={<Thermostat />}
                  label="Peak Event Intensity"
                  value={
                    peakTemperature == null
                      ? '—'
                      : `${peakTemperature.toFixed(1)}°C`
                  }
                  helper="Highest peak among detected events"
                />
                <MetricCard
                  icon={<TrendingUp />}
                  label="Long-term heatwave trend"
                  value={trendSlopeLabel}
                  helper={trendHeadline?.n_years >= 2
                    ? `Theil–Sen estimate · ${trendHeadline.start_year}–${trendHeadline.end_year}; descriptive, not significance-tested`
                    : "Insufficient annual observations to estimate a trend"}
                />
              </Box>

              {quality && (
                <Paper className="quality-strip" elevation={0}>
                  <Box>
                    <Typography fontWeight={700} variant="body2">
                      Analysis data quality
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {quality.requested_days} requested days ·{' '}
                      {quality.imputed_days} imputed ·{' '}
                      {quality.remaining_missing_days} missing after cleaning
                    </Typography>
                  </Box>
                  <Chip
                    size="small"
                    color={quality.analysis_ready ? 'success' : 'warning'}
                    label={
                      quality.analysis_ready
                        ? `${quality.source_completeness_percent}% complete`
                        : 'Review data quality'
                    }
                  />
                </Paper>
              )}

              <Box className="charts-grid">
                <Paper className="chart-card" elevation={0}>
                  <SectionHeading
                    title="Annual heatwave frequency"
                    subtitle="Number of detected events per year"
                  />
                  {trends.length ? (
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart
                        data={trends}
                        margin={{ top: 16, right: 8, left: -18, bottom: 0 }}
                      >
                        <CartesianGrid
                          stroke="#edf0f4"
                          strokeDasharray="3 3"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="year"
                          ticks={getYearTicks(trends)}
                          interval={0}
                          padding={{ left: 8, right: 20 }}
                          tickLine={false}
                          axisLine={false}
                          tickMargin={10}
                        />
                        <YAxis
                          allowDecimals={false}
                          tickLine={false}
                          axisLine={false}
                        />
                        <ChartTooltip contentStyle={chartTooltipStyle} />
                        <Bar
                          dataKey="heatwave_events"
                          name="Heatwave events"
                          fill="#c2410c"
                          radius={[6, 6, 0, 0]}
                          maxBarSize={46}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <Typography color="text.secondary">
                      No trend data for this range.
                    </Typography>
                  )}
                </Paper>

                <Paper className="chart-card" elevation={0}>
                  <SectionHeading
                    title="Heatwave duration"
                    subtitle="Annual event-attributed days; dashed line shows LOWESS smoothing"
                  />
                  {trends.length ? (
                    <ResponsiveContainer width="100%" height={280}>
                      <LineChart
                        data={trends}
                        margin={{ top: 16, right: 12, left: -18, bottom: 0 }}
                      >
                        <CartesianGrid
                          stroke="#edf0f4"
                          strokeDasharray="3 3"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="year"
                          ticks={getYearTicks(trends)}
                          interval={0}
                          padding={{ left: 8, right: 20 }}
                          tickLine={false}
                          axisLine={false}
                          tickMargin={10}
                        />
                        <YAxis
                          allowDecimals={false}
                          tickLine={false}
                          axisLine={false}
                        />
                        <ChartTooltip contentStyle={chartTooltipStyle} />
                        <Line
                          type="monotone"
                          dataKey="total_heatwave_days"
                          name="Observed heatwave days"
                          stroke="#0f766e"
                          strokeWidth={2.5}
                          dot={{ r: 3, fill: '#0f766e' }}
                          activeDot={{ r: 6 }}
                          connectNulls={false}
                        />
                        <Line
                          type="monotone"
                          dataKey="total_heatwave_days_lowess"
                          name="LOWESS smoothed trend"
                          stroke="#c2410c"
                          strokeWidth={2.5}
                          strokeDasharray="6 4"
                          dot={false}
                          activeDot={{ r: 5 }}
                          connectNulls={false}
                        />
                        <Legend />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <Typography color="text.secondary">
                      No trend data for this range.
                    </Typography>
                  )}
                </Paper>
              </Box>

              <Paper className="chart-card trend-table-card" elevation={0}>
                <SectionHeading
                  title="Year-by-year comparison"
                  subtitle="Annual metrics returned by the trends API"
                  action={<Stack direction="row" spacing={0.5} className="table-export-actions">
                    <Tooltip title="Export all annual metrics as CSV"><IconButton size="small" aria-label="Export trends CSV" onClick={() => downloadCsv('climatescope-annual-trends.csv', trendHeaders, trendRows)}><TableView fontSize="small" /></IconButton></Tooltip>
                    <Tooltip title="Export annual metrics as PDF"><IconButton size="small" aria-label="Export trends PDF" onClick={() => exportPdf('Annual heatwave trends', exportSubtitle, trendHeaders, trendRows)}><PictureAsPdf fontSize="small" /></IconButton></Tooltip>
                  </Stack>}
                />
                <Box className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Year</th>
                        <th>Events</th>
                        <th>Extreme</th>
                        <th>Heatwave days</th>
                        <th>Longest event</th>
                        <th>Peak temperature</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paginatedTrends.map((item) => (
                        <tr key={item.year}>
                          <td className="year-cell">{item.year}</td>
                          <td>{item.heatwave_events}</td>
                          <td>{item.extreme_heatwave_events}</td>
                          <td>{item.total_heatwave_days}</td>
                          <td>{item.longest_heatwave_days} days</td>
                          <td>
                            {item.peak_temperature_c == null
                              ? '—'
                              : `${Number(item.peak_temperature_c).toFixed(1)}°C`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Box>
                <PaginationBar page={trendPage} pageSize={rowsPerPage} total={trends.length} onChange={setTrendPage} />
              </Paper>
              </>}

              {activeTab === 'events' && <Paper className="chart-card events-card" elevation={0}>
                <SectionHeading
                  title={`Detected heatwave events · ${appliedFilters.startDate} to ${appliedFilters.endDate}`}
                  subtitle={`${events.length} detected event${events.length === 1 ? '' : 's'} in ${appliedFilters.location}`}
                  action={<Stack direction="row" spacing={0.5} alignItems="center" className="table-export-actions">
                    <Chip size="small" variant="outlined" label="Daily maximum temperature" />
                    <Tooltip title="Export all filtered events as CSV"><IconButton size="small" aria-label="Export events CSV" onClick={() => downloadCsv('climatescope-heatwave-events.csv', eventHeaders, eventRows)}><TableView fontSize="small" /></IconButton></Tooltip>
                    <Tooltip title="Export events table as PDF"><IconButton size="small" aria-label="Export events PDF" onClick={() => exportPdf('Heatwave events', exportSubtitle, eventHeaders, eventRows)}><PictureAsPdf fontSize="small" /></IconButton></Tooltip>
                  </Stack>}
                />

                {events.length ? (
                  <Box className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Start date</th>
                          <th>End date</th>
                          <th>Duration</th>
                          <th>Peak temperature</th>
                          <th>Mean temperature</th>
                          <th>Classification</th>
                          <th>Data quality</th>
                        </tr>
                      </thead>
                      <tbody>
                        {paginatedEvents.map((event) => (
                          <tr
                            key={`${event.start_date}-${event.end_date}`}
                          >
                            <td>{formatDate(event.start_date)}</td>
                            <td>{formatDate(event.end_date)}</td>
                            <td>{event.duration_days} days</td>
                            <td>
                              {Number(event.peak_temperature_c).toFixed(1)}°C
                            </td>
                            <td>
                              {Number(event.mean_temperature_c).toFixed(1)}°C
                            </td>
                            <td>
                              <Chip
                                size="small"
                                color={event.is_extreme ? 'error' : 'warning'}
                                label={event.is_extreme ? 'Extreme' : 'Moderate'}
                              />
                            </td>
                            <td>
                              <Chip
                                size="small"
                                variant="outlined"
                                color={
                                  event.contains_imputed_data
                                    ? 'warning'
                                    : 'success'
                                }
                                label={
                                  event.contains_imputed_data
                                    ? `${event.imputed_days} imputed`
                                    : 'Observed'
                                }
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </Box>
                ) : (
                  <Box className="empty-state">
                    <Whatshot sx={{ fontSize: 32 }} />
                    <Typography fontWeight={700}>
                      No heatwave events detected
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      No events met the detection criteria within the selected dates.
                    </Typography>
                  </Box>
                )}
                <PaginationBar page={eventsPage} pageSize={rowsPerPage} total={events.length} onChange={setEventsPage} />
              </Paper>}

              {activeTab === 'methodology' && <Box className="methodology-page">
                <Paper className="chart-card" elevation={0}>
                  <Typography variant="h6">Data source and detection method</Typography>
                  <Typography color="text.secondary">ERA5-Land daily maximum temperatures are compared against a 1991–2020 climatological baseline using rolling 5-day calendar windows.</Typography>
                  <Box className="methodology-facts">
                    <Box><Typography variant="h6">P90</Typography><Typography variant="body2" color="text.secondary">Moderate heatwave threshold</Typography></Box>
                    <Box><Typography variant="h6">P95</Typography><Typography variant="body2" color="text.secondary">Extreme heatwave threshold</Typography></Box>
                    <Box><Typography variant="h6">3+ days</Typography><Typography variant="body2" color="text.secondary">Minimum consecutive duration</Typography></Box>
                  </Box>
                  <Typography variant="body2" color="text.secondary">Moderate heatwaves require at least three consecutive days at or above P90; extreme periods use P95. Missing daily values may be interpolated for short gaps and are identified in event-level quality labels. Annual trend statistics are grouped by the event start year, while the event list and overview summary use the exact selected dates.</Typography>
                  <Typography variant="h6" sx={{ mt: 3, mb: 1 }}>Trend estimation and interpretation</Typography>
                  <Typography variant="body2" color="text.secondary">The headline rate uses the Theil–Sen estimator: the median of pairwise annual slopes, expressed as heatwave days per decade. The dashed chart line uses LOWESS to smooth local variation. These are descriptive analyses; statistical significance is not tested. Cross-year events are attributed entirely to their start year, and overflow days are tracked separately, so annual duration is event-attributed duration rather than the number of heatwave days physically occurring within each calendar year.</Typography>
                </Paper>
              </Box>}
            </>
          )}

          <Box className="footer">
            <Typography variant="caption" color="text.secondary">
              ClimateScope · Historical climate analysis · Not a real-time
              weather forecast
            </Typography>
            {lastUpdated && (
              <Typography variant="caption" color="text.secondary">
                Updated at{' '}
                {lastUpdated.toLocaleTimeString('en-IN', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </Typography>
            )}
          </Box>
        </Container>
      </Box>
    </ThemeProvider>
    </LocalizationProvider>
  );
}

export default App;
