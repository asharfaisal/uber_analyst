export default function KpiCards({ summary, highlightKey }) {
  if (!summary) return null

  const cards = [
    { key: 'total_rides', label: 'Total rides', value: summary.total_rides?.toLocaleString() },
    { key: 'completion_rate', label: 'Completion rate', value: `${summary.completion_rate}%` },
    { key: 'total_revenue', label: 'Total revenue', value: `₹${Math.round(summary.total_revenue).toLocaleString()}` },
    { key: 'avg_booking_value', label: 'Avg booking value', value: `₹${summary.avg_booking_value?.toFixed(0)}` },
    { key: 'avg_ride_distance', label: 'Avg ride distance', value: `${summary.avg_ride_distance?.toFixed(1)} km` },
    { key: 'avg_driver_rating', label: 'Avg driver rating', value: `${summary.avg_driver_rating} ★` },
    { key: 'avg_customer_rating', label: 'Avg customer rating', value: `${summary.avg_customer_rating} ★` },
    { key: 'unique_customers', label: 'Total customers', value: summary.unique_customers?.toLocaleString() },
  ]

  // When the question asked about one specific stat, show only that card
  // (full-width, emphasized) instead of the whole grid.
  if (highlightKey) {
    const match = cards.find((c) => c.key === highlightKey)
    if (match) {
      return (
        <div className="kpi-grid kpi-grid-single">
          <div className="kpi-card kpi-card-highlight" key={match.key}>
            <div className="kpi-value">{match.value}</div>
            <div className="kpi-label">{match.label}</div>
          </div>
        </div>
      )
    }
  }

  return (
    <div className="kpi-grid">
      {cards
        .filter((c) => c.key !== 'unique_customers' && c.key !== 'avg_customer_rating')
        .map((c) => (
          <div className="kpi-card" key={c.key}>
            <div className="kpi-value">{c.value}</div>
            <div className="kpi-label">{c.label}</div>
          </div>
        ))}
    </div>
  )
}