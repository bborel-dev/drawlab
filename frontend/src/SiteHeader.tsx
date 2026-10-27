function SiteHeader() {
  return (
    <header className="site-header glass">
      <span className="brand">Drawlab</span>
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
