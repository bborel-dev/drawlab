import { useEffect, useState } from 'react'
import { fetchQuota, onQuotaChange, type Allowance, type Quota } from './api'
import { ChevronIcon } from './icons'

const COLLAPSED_KEY = 'drawlab.quota-collapsed'

function QuotaBanner() {
  const quota = useQuota()
  const [collapsed, setCollapsed] = useCollapsed()
  if (!quota) return null

  if (collapsed) {
    return (
      <button
        type="button"
        className="quota quota-collapsed glass"
        aria-expanded={false}
        aria-label="Show what is left today"
        title={`${quota.conversions.left} conversions and ${quota.edits.left} AI edits left today`}
        onClick={() => setCollapsed(false)}
      >
        {quota.open ? (
          <span>
            <strong>{quota.conversions.left}</strong> · <strong>{quota.edits.left}</strong> left
          </span>
        ) : (
          <span className="quota-closed">Come back tomorrow</span>
        )}
        <span className="quota-chevron quota-chevron-up" aria-hidden="true">
          <ChevronIcon />
        </span>
      </button>
    )
  }

  return (
    <section className="quota quota-card glass" aria-label="Left today">
      <header className="quota-header">
        <span className="quota-title">Left today</span>
        <button
          type="button"
          className="icon-button quota-chevron"
          aria-expanded={true}
          aria-label="Collapse"
          onClick={() => setCollapsed(true)}
        >
          <ChevronIcon />
        </button>
      </header>
      {quota.open ? (
        <>
          <QuotaRow label="Conversions" allowance={quota.conversions} />
          <QuotaRow label="AI edits" allowance={quota.edits} />
        </>
      ) : (
        <p className="quota-closed">Daily budget reached, come back tomorrow</p>
      )}
    </section>
  )
}

function QuotaRow({ label, allowance }: { label: string; allowance: Allowance }) {
  return (
    <div className={allowance.left === 0 ? 'quota-row is-empty' : 'quota-row'}>
      <span>{label}</span>
      <span className="quota-count">
        <strong>{allowance.left}</strong>/{allowance.limit}
      </span>
    </div>
  )
}

function useQuota(): Quota | null {
  const [quota, setQuota] = useState<Quota | null>(null)
  useEffect(() => {
    let controller = new AbortController()
    const refresh = () => {
      controller.abort()
      controller = new AbortController()
      fetchQuota(controller.signal)
        .then(setQuota)
        .catch(() => undefined)
    }
    refresh()
    const unsubscribe = onQuotaChange(refresh)
    return () => {
      unsubscribe()
      controller.abort()
    }
  }, [])
  return quota
}

function useCollapsed(): [boolean, (collapsed: boolean) => void] {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  function change(next: boolean) {
    setCollapsed(next)
    try {
      localStorage.setItem(COLLAPSED_KEY, String(next))
    } catch {
      return
    }
  }
  return [collapsed, change]
}

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === 'true'
  } catch {
    return false
  }
}

export default QuotaBanner
