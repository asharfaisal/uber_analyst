import { BarChart as RBarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const GREEN = '#8BCF00'

export default function BarChart({ labels, values, unit }) {
  if (!labels?.length) return null

  const data = labels.map((label, i) => ({ name: label, value: values[i] }))

  return (
    <div style={{ width: '100%', height: Math.max(labels.length * 44, 180) }}>
      <ResponsiveContainer width="100%" height="100%">
        <RBarChart data={data} layout="vertical" margin={{ top: 0, right: 30, left: 8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#E5E5E2" />
          <XAxis type="number" tick={{ fontSize: 11, fill: '#6B6B6B' }} axisLine={false} tickLine={false} />
          <YAxis
            type="category"
            dataKey="name"
            width={110}
            tick={{ fontSize: 12, fill: '#171717' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(v) => [formatValue(v, unit), '']}
            contentStyle={{ borderRadius: 8, border: '1px solid #E5E5E2', fontSize: 12 }}
          />
          <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={28}>
            {data.map((_, i) => (
              <Cell key={i} fill={i === 0 ? GREEN : '#B7E38A'} />
            ))}
          </Bar>
        </RBarChart>
      </ResponsiveContainer>
    </div>
  )
}

function formatValue(value, unit) {
  const num = Number(value)
  const formatted = Number.isInteger(num) ? num.toLocaleString() : num.toFixed(2)
  if (unit === '₹') return `₹${formatted}`
  if (unit) return `${formatted} ${unit}`
  return formatted
}
