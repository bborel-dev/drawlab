import { useState, type CSSProperties } from 'react'

function Backdrop() {
  const [clock] = useState(() => ({ '--backdrop-delay': `${-performance.now()}ms` }) as CSSProperties)
  return (
    <div className="backdrop" style={clock} aria-hidden="true">
      <span className="blob blob-blue" />
      <span className="blob blob-pink" />
      <span className="blob blob-violet" />
      <span className="blob blob-cyan" />
      <span className="blob blob-orange" />
    </div>
  )
}

export default Backdrop
