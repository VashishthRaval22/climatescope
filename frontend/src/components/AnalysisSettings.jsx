import { useEffect } from 'react';
import {
  Autocomplete, Box, Button, Chip, Paper, Stack, TextField, Typography,
} from '@mui/material';
import { CalendarMonth, LocationOn, MapOutlined, Search } from '@mui/icons-material';
import { MapContainer, TileLayer, Marker, useMapEvents, useMap } from 'react-leaflet';
import L from 'leaflet';
import dayjs from 'dayjs';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';

const markerIcon = new L.Icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
});

function MapClickHandler({ onSelect }) {
  useMapEvents({ click(event) { onSelect(event.latlng.lat, event.latlng.lng); } });
  return null;
}

function MapCenter({ position }) {
  const map = useMap();
  useEffect(() => { map.setView(position, Math.max(map.getZoom(), 7)); }, [map, position[0], position[1]]);
  return null;
}

export default function AnalysisSettings({ latitude, setLatitude, longitude, setLongitude, cityQuery, setCityQuery,
  cityOptions, cityLoading, startDate, setStartDate, endDate, setEndDate,
  loading, analysis, filtersDirty, loadDashboard, showMap, setShowMap, chooseMapPoint }) {
  return (
    <Paper className="filter-panel" elevation={0}>
      <Box className="filter-panel-heading">
        <Box className="filter-title">
          <Search fontSize="small" />
          <Box>
            <Typography fontWeight={700}>Analysis settings</Typography>
            <Typography variant="body2" color="text.secondary">
              Define the region and period for your climate hazard analysis.
            </Typography>
          </Box>
        </Box>
        <Chip size="small" variant="outlined" label="ERA5-Land · Heatwaves" className="filter-method-chip" />
      </Box>

      <Box
        component="form"
        className="filter-grid"
        onSubmit={(event) => {
          event.preventDefault();
          loadDashboard();
        }}
      >
        <Box className="filter-location-section">
          <Box className="filter-section-label">
            <LocationOn fontSize="small" />
            <Typography variant="subtitle2">Location</Typography>
          </Box>
          <Autocomplete
          className="city-search-field"
          options={cityOptions}
          loading={cityLoading}
          filterOptions={(options) => options}
          getOptionLabel={(option) => typeof option === 'string' ? option : option.label ?? ''}
          isOptionEqualToValue={(option, value) => option.id === value.id}
          inputValue={cityQuery}
          onInputChange={(_, value, reason) => {
            if (reason === 'input' || reason === 'clear') setCityQuery(value);
          }}
          onChange={(_, place) => {
            if (!place) return;
            setCityQuery(place.label);
            setLatitude(String(place.latitude));
            setLongitude(String(place.longitude));
          }}
          noOptionsText={cityQuery.trim().length < 2 ? 'Type at least 2 characters' : 'No matching places'}
          loadingText="Searching cities…"
          renderOption={(props, option) => (
            <li {...props} key={`${option.id}-${option.label}`}>
              <Box>
                <Typography variant="body2" fontWeight={600}>{option.name}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {[option.admin1, option.country].filter(Boolean).join(', ')}
                </Typography>
              </Box>
            </li>
          )}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Search city or region"
              placeholder="e.g. Ahmedabad, Gujarat"
              size="small"
              fullWidth
              helperText="Select a result to update the coordinates"
            />
          )}
        />
        </Box>
        <Box className="filter-details-section">
          <Box className="filter-section-label">
            <CalendarMonth fontSize="small" />
            <Typography variant="subtitle2">Coordinates and analysis period</Typography>
          </Box>
          <Box className="filter-fields-grid">
        <TextField
          label="Latitude"
          value={latitude}
          onChange={(event) => {
            setLatitude(event.target.value);
            setCityQuery('');
          }}
          type="number"
          slotProps={{ htmlInput: { step: 'any', min: -90, max: 90 } }}
          size="small"
          fullWidth
        />
        <TextField
          label="Longitude"
          value={longitude}
          onChange={(event) => {
            setLongitude(event.target.value);
            setCityQuery('');
          }}
          type="number"
          slotProps={{ htmlInput: { step: 'any', min: -180, max: 180 } }}
          size="small"
          fullWidth
        />
        <DatePicker label="Start date" value={dayjs(startDate)} minDate={dayjs('1950-01-01')} maxDate={dayjs('2025-12-31')} format="DD/MM/YYYY" onChange={(value) => { if (value?.isValid()) setStartDate(value.format('YYYY-MM-DD')); }} slotProps={{ textField: { size: 'small', fullWidth: true } }} />
        <DatePicker label="End date" value={dayjs(endDate)} minDate={dayjs('1950-01-01')} maxDate={dayjs('2025-12-31')} format="DD/MM/YYYY" onChange={(value) => { if (value?.isValid()) setEndDate(value.format('YYYY-MM-DD')); }} slotProps={{ textField: { size: 'small', fullWidth: true } }} />
        <Button
          type="submit"
          variant="contained"
          startIcon={<Search />}
          disabled={loading || (Boolean(analysis) && !filtersDirty)}
          className="analyze-button"
        >
          {loading ? 'Analyzing…' : analysis && !filtersDirty ? 'Analysis up to date' : 'Analyze'}
        </Button>
          </Box>
        </Box>
      </Box>
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        className="location-note"
      >
        <LocationOn fontSize="small" />
        <Typography variant="caption" color="text.secondary">
          Choose a city and date range, then Analyze. Editing settings never runs analysis automatically; Analyze becomes available when your inputs differ from the last successful run.
        </Typography>
      </Stack>
      <Box className="map-picker-toggle">
        <Box className="map-picker-copy">
          <Box className="map-picker-icon"><MapOutlined /></Box>
          <Box>
            <Typography variant="body2" fontWeight={700}>Choose location on map</Typography>
            <Typography variant="caption" color="text.secondary">
              Select a point to set its coordinates directly.
            </Typography>
          </Box>
        </Box>
        <Button size="small" variant={showMap ? "contained" : "outlined"} startIcon={<MapOutlined />} onClick={() => setShowMap((value) => !value)}>
          {showMap ? 'Hide map' : 'Open map'}
        </Button>
      </Box>
      {showMap && <Box className="map-picker-wrap">
        <MapContainer center={[Number(latitude) || 19.076, Number(longitude) || 72.8777]} zoom={5} scrollWheelZoom className="location-map">
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <MapCenter position={[Number(latitude) || 19.076, Number(longitude) || 72.8777]} />
          <MapClickHandler onSelect={chooseMapPoint} />
          <Marker position={[Number(latitude) || 19.076, Number(longitude) || 72.8777]} icon={markerIcon} />
        </MapContainer>
        <Typography variant="caption" color="text.secondary">Selected point: {Number(latitude).toFixed(5)}, {Number(longitude).toFixed(5)}. The map sets a coordinate; it does not infer a city name.</Typography>
      </Box>}
    </Paper>
  );
}
