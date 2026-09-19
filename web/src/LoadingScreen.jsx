import logoSrc from './assets/uber-intelligence-logo.png'
import carSrc from './assets/IntercityComfort-1.png'

export default function LoadingScreen({ fadingOut }) {
  return (
    <div
      className={`fixed inset-0 z-50 min-h-screen w-full flex flex-col items-center justify-center bg-white ${
        fadingOut ? 'animate-screen-out' : ''
      }`}
      style={{ fontFamily: "'Inter', system-ui, sans-serif" }}
    >
      <div className="animate-logo flex flex-col items-center gap-3">
        <img
          src={logoSrc}
          alt="Ride Intelligence"
          style={{ width: 180, height: 'auto', filter: 'invert(1)' }}
          draggable={false}
        />
        <span
          style={{
            color: 'rgba(0,0,0,0.4)',
            fontSize: '11px',
            fontWeight: 500,
            letterSpacing: '0.22em',
            textTransform: 'uppercase',
          }}
        >
          Intelligence
        </span>
      </div>

      <div className="animate-text flex items-center justify-center" style={{ marginTop: 48 }}>
        <img
          src={carSrc}
          alt=""
          style={{ width: 260, height: 'auto' }}
          draggable={false}
        />
      </div>

      <p
        className="animate-text"
        style={{
          marginTop: 36,
          color: 'rgba(0,0,0,0.45)',
          fontSize: '13px',
          fontWeight: 300,
          letterSpacing: '0.03em',
        }}
      >
        Preparing your insights…
      </p>

      <div
        className="animate-dots"
        style={{ marginTop: 24, display: 'flex', gap: 7, alignItems: 'center' }}
      >
        <span className="dot-1" style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: 'rgba(0,0,0,0.35)', display: 'block' }} />
        <span className="dot-2" style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: 'rgba(0,0,0,0.35)', display: 'block' }} />
        <span className="dot-3" style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: 'rgba(0,0,0,0.35)', display: 'block' }} />
      </div>
    </div>
  )
}
