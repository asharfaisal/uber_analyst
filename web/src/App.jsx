import { useState, useRef, useEffect } from 'react'
import BarChart from './BarChart.jsx'
import LineChart from './LineChart.jsx'
import KpiCards from './KpiCards.jsx'

const SUGGESTED_QUESTIONS = [
  'Give me an overview of the business',
  'What were the top 5 vehicle types by ride count?',
  'Compare Auto and Go Sedan revenue',
  'Show the ride volume trend by month',
  'Why do drivers cancel rides?',
]

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function ask(question) {
    if (!question.trim() || loading) return

    setMessages((m) => [...m, { role: 'user', text: question }])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      const data = await res.json()

      if (!res.ok) {
        setMessages((m) => [...m, { role: 'assistant', error: data.error || 'Something went wrong.' }])
      } else if (data.needs_clarification) {
        setMessages((m) => [...m, { role: 'assistant', clarification: data.clarification_question }])
      } else {
        setMessages((m) => [...m, { role: 'assistant', result: data }])
      }
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', error: 'Could not reach the server. Please try again.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Uber AI Analyst</h1>
        <p>Delhi/NCR ride data · Jan – Dec 2025</p>
      </header>

      <main className="chat-area">
        {messages.length === 0 && (
          <div className="welcome">
            <p>Ask a question about the ride data to get started.</p>
            <div className="suggestions">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button key={q} className="suggestion-chip" onClick={() => ask(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.role === 'user' && <div className="bubble user-bubble">{msg.text}</div>}

            {msg.role === 'assistant' && msg.error && (
              <div className="bubble error-bubble">{msg.error}</div>
            )}

            {msg.role === 'assistant' && msg.clarification && (
              <div className="bubble assistant-bubble">{msg.clarification}</div>
            )}

            {msg.role === 'assistant' && msg.result && (
              <div className="bubble assistant-bubble result-bubble">
                <p className="narrative">{msg.result.narrative}</p>

                {msg.result.chart_type === 'kpi_cards' && (
                  <KpiCards summary={msg.result.raw_summary} />
                )}
                {msg.result.chart_type === 'bar' && (
                  <>
                    <h3 className="chart-title">{msg.result.title}</h3>
                    <BarChart
                      labels={msg.result.labels}
                      values={msg.result.values}
                      unit={msg.result.unit}
                    />
                  </>
                )}
                {msg.result.chart_type === 'line' && (
                  <>
                    <h3 className="chart-title">{msg.result.title}</h3>
                    <LineChart
                      labels={msg.result.labels}
                      values={msg.result.values}
                      unit={msg.result.unit}
                    />
                  </>
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="message assistant">
            <div className="bubble assistant-bubble loading-bubble">Analyzing…</div>
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      <footer className="input-bar">
        <input
          type="text"
          placeholder="Ask anything about the ride data..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && ask(input)}
          disabled={loading}
        />
        <button onClick={() => ask(input)} disabled={loading || !input.trim()}>
          Send
        </button>
      </footer>
    </div>
  )
}
