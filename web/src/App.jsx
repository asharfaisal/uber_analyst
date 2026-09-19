import { useState, useRef, useEffect } from 'react'
import BarChart from './BarChart.jsx'
import LineChart from './LineChart.jsx'
import KpiCards from './KpiCards.jsx'
import LoadingScreen from './LoadingScreen.jsx'
import logoSrc from './assets/uber-intelligence-logo.png'

const SUGGESTED_QUESTIONS = [
  { icon: '📊', label: 'Give me an overview of the business' },
  { icon: '🏆', label: 'What are the top 5 vehicle types by ride count?' },
  { icon: '📈', label: 'Show the ride volume trend by month' },
  { icon: '📍', label: 'Which pickup location has the most rides?' },
]

const HISTORY_ICONS = ['📊', '🚕', '📍', '🚗', '💳', '❌', '⏱️']

export default function App() {
  const [showLoading, setShowLoading] = useState(true)
  const [fadingOut, setFadingOut] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    const fadeTimer = setTimeout(() => setFadingOut(true), 1900)
    const hideTimer = setTimeout(() => setShowLoading(false), 2300)
    return () => {
      clearTimeout(fadeTimer)
      clearTimeout(hideTimer)
    }
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function ask(question) {
    if (!question.trim() || loading) return

    setMessages((m) => [...m, { role: 'user', text: question }])
    setInput('')
    setLoading(true)

    const history = []
    for (let i = 0; i < messages.length; i++) {
      const m = messages[i]
      if (m.role === 'assistant' && m.result && i > 0) {
        const prevUserMsg = messages[i - 1]
        if (prevUserMsg.role === 'user') {
          history.push({ question: prevUserMsg.text, narrative: m.result.narrative })
        }
      }
    }
    const recentHistory = history.slice(-5)

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, history: recentHistory }),
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

  const askedQuestions = messages.filter((m) => m.role === 'user').map((m) => m.text)

  return (
    <div className="flex h-screen w-full bg-[#F5F5F3]" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
      {showLoading && <LoadingScreen fadingOut={fadingOut} />}

      {/* Sidebar */}
      <aside className="w-[260px] shrink-0 bg-[#111111] flex flex-col dark-scroll">
        <div className="px-5 py-6 flex items-center gap-2">
          <img src={logoSrc} alt="" style={{ width: 24, height: 24, filter: 'invert(1)' }} />
          <div>
            <div className="text-white text-sm font-semibold tracking-wide">Ride Intelligence</div>
            <div className="text-[10px] text-white/40 tracking-wider uppercase">AI Business Analytics</div>
          </div>
        </div>

        <div className="px-4">
          <button
            onClick={() => setMessages([])}
            className="w-full rounded-lg py-2.5 text-sm font-medium mb-6 transition-colors"
            style={{ backgroundColor: '#8BCF00', color: '#111111' }}
          >
            + New Analysis
          </button>
        </div>

        <div className="px-5 text-[11px] uppercase tracking-wider text-white/30 mb-2">Recent Analysis</div>
        <div className="flex-1 overflow-y-auto px-3 dark-scroll">
          {askedQuestions.length === 0 && (
            <div className="px-2 py-1 text-[13px] text-white/25">No questions yet</div>
          )}
          {askedQuestions.map((q, i) => (
            <div
              key={i}
              className="flex items-center gap-2 px-2 py-2 rounded-lg text-[13px] text-white/70 hover:bg-white/5 truncate"
            >
              <span>{HISTORY_ICONS[i % HISTORY_ICONS.length]}</span>
              <span className="truncate">{q}</span>
            </div>
          ))}
        </div>

        <div className="px-4 py-4 border-t border-white/10 flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold shrink-0"
            style={{ backgroundColor: '#8BCF00', color: '#111111' }}
          >
            MA
          </div>
          <div>
            <div className="text-[12px] text-white/80 font-medium">Muhammad Ashar</div>
            <div className="text-[10px] text-white/35">Data Analyst</div>
          </div>
        </div>
      </aside>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="px-8 py-5 border-b border-[#E5E5E2] flex items-center justify-between shrink-0">
          <div>
            <h1 className="text-lg font-semibold text-[#171717]">AI Business Analyst</h1>
            <p className="text-[12px] text-[#6B6B6B]">Delhi/NCR ride data · Jan – Dec 2025</p>
          </div>
          <div className="flex items-center gap-1.5 text-[12px] text-[#6B6B6B]">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#8BCF00' }} />
            AI Ready
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-8 py-6 flex flex-col gap-4">
          {messages.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center text-center">
              <p className="text-2xl font-semibold text-[#171717] mb-1">Good day 👋</p>
              <p className="text-[#6B6B6B] mb-6">What would you like to know about your business?</p>
              <div className="grid grid-cols-2 gap-3 max-w-xl w-full">
                {SUGGESTED_QUESTIONS.map((s) => (
                  <button
                    key={s.label}
                    onClick={() => ask(s.label)}
                    className="text-left px-4 py-3 rounded-xl bg-white border border-[#E5E5E2] text-[13px] text-[#171717] hover:border-[#8BCF00] transition-colors"
                  >
                    <span className="mr-2">{s.icon}</span>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'user' && (
                <div className="max-w-[75%] rounded-2xl px-4 py-2.5 text-[14px]" style={{ backgroundColor: '#8BCF00', color: '#111111' }}>
                  {msg.text}
                </div>
              )}

              {msg.role === 'assistant' && msg.error && (
                <div className="max-w-[90%] rounded-2xl px-4 py-3 text-[14px] bg-red-50 border border-red-200 text-red-700">
                  {msg.error}
                </div>
              )}

              {msg.role === 'assistant' && msg.clarification && (
                <div className="max-w-[90%] rounded-2xl px-4 py-3 text-[14px] bg-white border border-[#E5E5E2] text-[#171717]">
                  {msg.clarification}
                </div>
              )}

              {msg.role === 'assistant' && msg.result && (
                <div className="w-full max-w-2xl rounded-2xl px-5 py-4 bg-white border border-[#E5E5E2]">
                  <p className="text-[14px] text-[#171717] mb-4 leading-relaxed">{msg.result.narrative}</p>

                  {msg.result.chart_type === 'kpi_cards' && (
                    <KpiCards summary={msg.result.raw_summary} highlightKey={msg.result.highlighted_key} />
                  )}
                  {msg.result.chart_type === 'bar' && (
                    <>
                      <h3 className="text-[12px] font-semibold text-[#6B6B6B] mb-3 uppercase tracking-wide">{msg.result.title}</h3>
                      <BarChart labels={msg.result.labels} values={msg.result.values} unit={msg.result.unit} />
                    </>
                  )}
                  {msg.result.chart_type === 'line' && (
                    <>
                      <h3 className="text-[12px] font-semibold text-[#6B6B6B] mb-3 uppercase tracking-wide">{msg.result.title}</h3>
                      <LineChart labels={msg.result.labels} values={msg.result.values} unit={msg.result.unit} />
                    </>
                  )}
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="rounded-2xl px-4 py-3 bg-white border border-[#E5E5E2] text-[13px] text-[#6B6B6B] italic">
                Analyzing…
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </main>

        <footer className="px-8 py-5 border-t border-[#E5E5E2] shrink-0">
          <div className="flex items-center gap-2 max-w-3xl">
            <input
              type="text"
              placeholder="Ask anything about your business data..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && ask(input)}
              disabled={loading}
              className="flex-1 rounded-full px-4 py-2.5 text-[14px] border border-[#E5E5E2] outline-none focus:border-[#8BCF00] bg-white"
            />
            <button
              onClick={() => ask(input)}
              disabled={loading || !input.trim()}
              className="rounded-full px-5 py-2.5 text-[14px] font-medium disabled:opacity-40"
              style={{ backgroundColor: '#8BCF00', color: '#111111' }}
            >
              Send
            </button>
          </div>
        </footer>
      </div>
    </div>
  )
}
