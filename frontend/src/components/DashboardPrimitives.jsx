import { Box, Button, Paper, Skeleton, Typography } from '@mui/material';

function MetricCard({ icon, label, value, helper }) {
  return (
    <Paper className="metric-card" elevation={0}>
      <Box className="metric-card-top">
        <Box className="metric-icon">{icon}</Box>
        <Typography variant="body2" color="text.secondary">
          {label}
        </Typography>
      </Box>
      <Typography className="metric-value">{value}</Typography>
      <Typography variant="caption" color="text.secondary">
        {helper}
      </Typography>
    </Paper>
  );
}

function SectionHeading({ title, subtitle, action }) {
  return (
    <Box className="section-heading">
      <Box>
        <Typography variant="h6">{title}</Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </Box>
      {action}
    </Box>
  );
}


function PaginationBar({ page, pageSize, total, onChange }) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  if (total === 0) return null;

  const first = page * pageSize + 1;
  const last = Math.min((page + 1) * pageSize, total);

  return (
    <Box className="pagination-bar">
      <Typography
        variant="body2"
        color="text.secondary"
        className="pagination-summary"
      >
        Showing <strong>{first}–{last}</strong> of {total}
      </Typography>

      {pageCount > 1 && (
        <Box className="pagination-actions">
          <Button
            size="small"
            variant="outlined"
            disabled={page === 0}
            onClick={() => onChange(page - 1)}
          >
            Previous
          </Button>

          <Typography
            variant="body2"
            color="text.secondary"
            className="pagination-page-label"
          >
            Page {page + 1} of {pageCount}
          </Typography>

          <Button
            size="small"
            variant="outlined"
            disabled={page + 1 >= pageCount}
            onClick={() => onChange(page + 1)}
          >
            Next
          </Button>
        </Box>
      )}
    </Box>
  );
}

function SkeletonDashboard() {
  return <Box className="skeleton-dashboard" aria-label="Loading climate analysis" aria-busy="true">
    <Box className="metrics-grid">{[1, 2, 3, 4].map((n) => <Paper className="metric-card" elevation={0} key={n}>
      <Skeleton variant="rounded" width={38} height={38} />
      <Skeleton variant="text" width="55%" height={22} sx={{ mt: 1 }} />
      <Skeleton variant="text" width="42%" height={42} />
      <Skeleton variant="text" width="72%" />
    </Paper>)}</Box>
    <Paper className="quality-strip" elevation={0}><Box sx={{ width: '60%' }}><Skeleton width="35%" /><Skeleton width="80%" /></Box><Skeleton width={90} /></Paper>
    <Box className="charts-grid">{[1, 2].map((n) => <Paper className="chart-card" elevation={0} key={n}>
      <Skeleton variant="text" width="48%" height={28} /><Skeleton variant="text" width="35%" />
      <Skeleton variant="rounded" height={230} sx={{ mt: 2 }} />
    </Paper>)}</Box>
    <Paper className="chart-card" elevation={0}><Skeleton variant="text" width="32%" height={28} />
      {[1, 2, 3, 4, 5].map((n) => <Skeleton key={n} variant="rounded" height={34} sx={{ my: 1 }} />)}
    </Paper>
  </Box>;
}

function AnimatedWords({ text }) {
  const words = text.split(/\s+/).filter(Boolean);

  return (
    <Typography
      variant="body2"
      color="text.secondary"
      className="loading-animated-copy"
      aria-label={text}
      role="status"
      aria-live="polite"
    >
      <span className="loading-animated-copy-visual" aria-hidden="true">
        {words.map((word, index) => (
          <span
            className="loading-word"
            key={`${word}-${index}`}
            style={{ animationDelay: `${Math.min(index * 75, 1800)}ms` }}
          >
            {word}{index < words.length - 1 ? ' ' : ''}
          </span>
        ))}
      </span>
    </Typography>
  );
}


export { MetricCard, SectionHeading, PaginationBar, SkeletonDashboard, AnimatedWords };
