export default function BarChart({ labels, values, unit }) {
  if (!labels?.length) return null

  const width = 640
  const barHeight = 32
  const gap = 12
  const labelWidth = 160
  const chartAreaWidth = width - labelWidth - 70
  const maxValue = Math.max(...values, 1)
  const height = labels.length * (barHeight + gap) + gap

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Bar chart">
      {labels.map((label, i) => {
        const y = gap + i * (barHeight + gap)
        const barWidth = (values[i] / maxValue) * chartAreaWidth
        return (
          <g key={label}>
            <text
              x={labelWidth - 10}
              y={y + barHeight / 2}
              textAnchor="end"
              dominantBaseline="central"
              fontSize="13"
              fill="#3d3d3a"
            >
              {label.length > 20 ? label.slice(0, 18) + '…' : label}
            </text>
            <rect
              x={labelWidth}
              y={y}
              width={Math.max(barWidth, 2)}
              height={barHeight}
              rx="4"
              fill="#1D9E75"
            />
            <text
              x={labelWidth + barWidth + 8}
              y={y + barHeight / 2}
              dominantBaseline="central"
              fontSize="12"
              fill="#5f5e5a"
            >
              {formatValue(values[i], unit)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function formatValue(value, unit) {
  const rounded = Number.isInteger(value) ? value : value.toFixed(2)
  const formatted = rounded.toLocaleString()
  if (unit === '₹') return `₹${formatted}`
  if (unit) return `${formatted} ${unit}`
  return formatted
}
