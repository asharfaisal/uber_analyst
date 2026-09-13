export default function KpiCards({ summary }) {
  if (!summary) return null

  const cards = [
    { label: 'Total rides', value: summary.total_rides?.toLocaleString() },
    { label: 'Completion rate', value: `${summary.completion_rate}%` },
    { label: 'Total revenue', value: `₹${Math.round(summary.total_revenue).toLocaleString()}` },
    { label: 'Avg booking value', value: `₹${summary.avg_booking_value?.toFixed(0)}` },
    { label: 'Avg ride distance', value: `${summary.avg_ride_distance?.toFixed(1)} km` },
    { label: 'Avg driver rating', value: `${summary.avg_driver_rating} ★` },
  ]

  return (
    <div className="kpi-grid">
      {cards.map((c) => (
        <div className="kpi-card" key={c.label}>
          <div className="kpi-value">{c.value}</div>
          <div className="kpi-label">{c.label}</div>
        </div>
      ))}
    </div>
  )
}
