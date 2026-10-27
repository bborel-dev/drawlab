function SiteHeader() {
  return (
    <header className="site-header">
      <div className="brand">
        <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
          <circle cx="13" cy="13" r="13" fill="#0866FF" />
          <path
            d="M8 18 L15.5 10.5 M14 9 L17 12 M8 18 L7.4 19.6 L9 19"
            fill="none"
            stroke="#FFFFFF"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span>Drawlab</span>
      </div>
      <nav className="site-nav" aria-label="Pages">
        <span className="nav-item is-active" aria-current="page">
          Convert
        </span>
        <span className="nav-item is-disabled" title="Coming soon">
          Editor
        </span>
      </nav>
    </header>
  )
}

export default SiteHeader
