export default function LineChart({ labels, values, unit }) {
  if (!labels?.length) return null

  const width = 640
  const height = 260
  const padding = { top: 20, right: 20, bottom: 40, left: 60 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const maxValue = Math.max(...values, 1)
  const minValue = Math.min(...values, 0)
  const range = maxValue - minValue || 1

  const points = values.map((v, i) => {
    const x = padding.left + (i / Math.max(values.length - 1, 1)) * chartWidth
    const y = padding.top + chartHeight - ((v - minValue) / range) * chartHeight
    return [x, y]
  })

  const pathD = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x} ${y}`).join(' ')

  const labelStep = Math.ceil(labels.length / 8)

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Line chart">
      <line
        x1={padding.left}
        y1={padding.top + chartHeight}
        x2={padding.left + chartWidth}
        y2={padding.top + chartHeight}
        stroke="#B4B2A9"
        strokeWidth="0.5"
      />
      <path d={pathD} fill="none" stroke="#1D9E75" strokeWidth="2" />
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
      <text
        x={padding.left - 8}
        y={padding.top + chartHeight}
        textAnchor="end"
        fontSize="11"
        fill="#5f5e5a"
      >
        {formatValue(minValue, unit)}
      </text>
    </svg>
  )
}

// Truncate on a word/character boundary that reads as an intentional
// abbreviation rather than a cut-off word -- "September" -> "Sep", not
// "Septembe". Full text is still available via the point's <title> tooltip.
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