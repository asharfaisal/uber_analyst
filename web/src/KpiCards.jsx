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

  if (highlightKey) {
    const match = cards.find((c) => c.key === highlightKey)
    if (match) {
      return (
        <div className="max-w-[220px]">
          <div className="rounded-xl p-5" style={{ backgroundColor: '#8BCF00' }}>
            <div className="text-2xl font-semibold" style={{ color: '#111111' }}>{match.value}</div>
            <div className="text-xs mt-1 font-medium" style={{ color: 'rgba(17,17,17,0.7)' }}>{match.label}</div>
          </div>
        </div>
      )
    }
  }

  return (
    <div className="grid grid-cols-3 gap-3">
      {cards
        .filter((c) => c.key !== 'unique_customers' && c.key !== 'avg_customer_rating')
        .map((c) => (
          <div key={c.key} className="rounded-xl p-4 bg-[#F5F5F3] border border-[#E5E5E2]">
            <div className="text-lg font-semibold" style={{ color: '#171717' }}>{c.value}</div>
            <div className="text-[11px] mt-1" style={{ color: '#6B6B6B' }}>{c.label}</div>
          </div>
        ))}
    </div>
  )
}
