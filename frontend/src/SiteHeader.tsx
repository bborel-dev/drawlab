import BrandMark from './BrandMark'

export type Page = 'convert' | 'editor'

type SiteHeaderProps = {
  page: Page
  onNavigate: (page: Page) => void
}

function SiteHeader({ page, onNavigate }: SiteHeaderProps) {
  return (
    <header className="site-header glass">
      <BrandMark />
      <nav className="site-nav" aria-label="Pages">
        <NavItem label="Convert" active={page === 'convert'} onClick={() => onNavigate('convert')} />
        <NavItem label="Editor" active={page === 'editor'} onClick={() => onNavigate('editor')} />
      </nav>
    </header>
  )
}

type NavItemProps = {
  label: string
  active: boolean
  disabled?: boolean
  title?: string
  onClick: () => void
}

function NavItem({ label, active, disabled = false, title, onClick }: NavItemProps) {
  return (
    <button
      type="button"
      className={`nav-item${active ? ' is-active' : ''}`}
      aria-current={active ? 'page' : undefined}
      disabled={disabled}
      title={title}
      onClick={onClick}
    >
      {label}
    </button>
  )
}

export default SiteHeader
