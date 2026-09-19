import { AreaChart as RAreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

const GREEN = '#8BCF00'

export default function LineChart({ labels, values, unit }) {
  if (!labels?.length) return null

  const data = labels.map((label, i) => ({ name: truncateLabel(String(label)), value: values[i] }))

  return (
    <div style={{ width: '100%', height: 240 }}>
      <ResponsiveContainer width="100%" height="100%">
        <RAreaChart data={data} margin={{ top: 8, right: 20, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={GREEN} stopOpacity={0.35} />
              <stop offset="100%" stopColor={GREEN} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E5E2" />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6B6B6B' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: '#6B6B6B' }} axisLine={false} tickLine={false} width={60} />
          <Tooltip
            formatter={(v) => [formatValue(v, unit), '']}
            contentStyle={{ borderRadius: 8, border: '1px solid #E5E5E2', fontSize: 12 }}
          />
          <Area type="monotone" dataKey="value" stroke={GREEN} strokeWidth={2} fill="url(#areaFill)" dot={{ r: 3, fill: GREEN }} />
        </RAreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function truncateLabel(label) {
  if (label.length <= 8) return label
  return label.slice(0, 3)
}

function formatValue(value, unit) {
  const num = Number(value)
  const formatted = Number.isInteger(num) ? num.toLocaleString() : num.toFixed(1)
  if (unit === '₹') return `₹${formatted}`
  if (unit) return `${formatted} ${unit}`
  return formatted
}
