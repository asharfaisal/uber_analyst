export default function LineChart({ labels, values, unit }) {
  if (!labels?.length) return null

  const width = 640
  const height = 260
  const padding = { top: 20, right: 20, bottom: 40, left: 60 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom
  const baselineY = padding.top + chartHeight

  const maxValue = Math.max(...values, 1)
  const minValue = Math.min(...values, 0)
  const range = maxValue - minValue || 1

  const points = values.map((v, i) => {
    const x = padding.left + (i / Math.max(values.length - 1, 1)) * chartWidth
    const y = padding.top + chartHeight - ((v - minValue) / range) * chartHeight
    return [x, y]
  })

  const lineD = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x} ${y}`).join(' ')

  // Area fill: trace the line, then drop straight down to the baseline at
  // the last point, run back along the baseline to the first point's x,
  // and close -- fills the region under the curve.
  const firstX = points[0][0]
  const lastX = points[points.length - 1][0]
  const areaD = `${lineD} L ${lastX} ${baselineY} L ${firstX} ${baselineY} Z`

  const labelStep = Math.ceil(labels.length / 8)
  const gradientId = 'lineChartAreaGradient'

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Area chart">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1D9E75" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#1D9E75" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      <line
        x1={padding.left}
        y1={baselineY}
        x2={padding.left + chartWidth}
        y2={baselineY}
        stroke="#B4B2A9"
        strokeWidth="0.5"
      />

      <path d={areaD} fill={`url(#${gradientId})`} stroke="none" />
      <path d={lineD} fill="none" stroke="#1D9E75" strokeWidth="2" />

      {points.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="3" fill="#1D9E75">
          <title>{`${labels[i]}: ${values[i]}${unit ? ' ' + unit : ''}`}</title>
        </circle>
      ))}

      {labels.map((label, i) =>
        i % labelStep === 0 ? (
          <text
            key={label}
            x={points[i][0]}
            y={height - 15}
            textAnchor="middle"
            fontSize="11"
            fill="#5f5e5a"
          >
            {truncateLabel(String(label))}
          </text>
        ) : null
      )}

      <text x={padding.left - 8} y={padding.top} textAnchor="end" fontSize="11" fill="#5f5e5a">
        {formatValue(maxValue, unit)}
      </text>
      <text x={padding.left - 8} y={baselineY} textAnchor="end" fontSize="11" fill="#5f5e5a">
        {formatValue(minValue, unit)}
      </text>
    </svg>
  )
}

function truncateLabel(label) {
  if (label.length <= 8) return label
  return label.slice(0, 3)
}

function formatValue(value, unit) {
  const rounded = Number.isInteger(value) ? value : value.toFixed(1)
  const formatted = rounded.toLocaleString()
  if (unit === '₹') return `₹${formatted}`
  if (unit) return `${formatted} ${unit}`
  return formatted
}