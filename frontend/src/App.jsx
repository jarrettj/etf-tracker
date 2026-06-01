import React from 'react';
import { createRoot } from 'react-dom/client';

const API = '';

// ── Theme ────────────────────────────────────────────────────────────────────
function getInitialTheme() {
  const stored = localStorage.getItem('theme');
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
}

const ThemeContext = React.createContext();

function ThemeProvider({ children }) {
  const [theme, setThemeState] = React.useState(() => {
    const t = getInitialTheme();
    applyTheme(t);
    return t;
  });

  const toggle = React.useCallback(() => {
    setThemeState(prev => {
      const next = prev === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      localStorage.setItem('theme', next);
      return next;
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

function ThemeToggle() {
  const { theme, toggle } = React.useContext(ThemeContext);
  return (
    <button className="theme-toggle" onClick={toggle} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
      {theme === 'dark' ? '☀️' : '🌙'}
    </button>
  );
}

function formatZAR(n) {
  if (n === null || n === undefined || n === '-') return '-';
  return 'R ' + Number(n).toLocaleString('en-ZA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPct(n) {
  if (n === null || n === undefined) return '-';
  return Number(n).toFixed(2) + '%';
}

// ── SummaryCard ─────────────────────────────────────────────────────────────
function SummaryCard({ label, value, positive }) {
  return (
    <div className="summary-card">
      <div className="summary-label">{label}</div>
      <div className={`summary-value ${positive === true ? 'positive' : positive === false ? 'negative' : ''}`}>
        {value}
      </div>
    </div>
  );
}

// ── AddPositionForm ─────────────────────────────────────────────────────────
function AddPositionForm({ onAdded }) {
  const [ticker, setTicker] = React.useState('');
  const [shares, setShares] = React.useState('');
  const [cost, setCost] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!ticker.trim() || !shares) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/portfolio/positions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          etf_ticker: ticker.trim().toUpperCase(),
          shares: parseFloat(shares),
          cost_basis_per_share: parseFloat(cost) || 0,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setTicker('');
      setShares('');
      setCost('');
      onAdded?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="add-form">
      <h3>Add Position</h3>
      {error && <div className="error">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="Ticker (e.g. STXNDQ)" />
          <input type="number" step="any" value={shares} onChange={(e) => setShares(e.target.value)} placeholder="Shares" />
          <input type="number" step="any" value={cost} onChange={(e) => setCost(e.target.value)} placeholder="Cost basis / share (ZAR)" />
          <button type="submit" disabled={submitting || !ticker.trim() || !shares} className="btn-primary">
            {submitting ? 'Adding...' : 'Add'}
          </button>
        </div>
      </form>
    </div>
  );
}

// ── PortfolioPage ───────────────────────────────────────────────────────────
function PortfolioPage() {
  const [data, setData] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [selectedTicker, setSelectedTicker] = React.useState(null);

  const load = React.useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/portfolio`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  React.useEffect(() => { load(); }, [load]);

  const removePosition = async (p) => {
    if (!confirm(`Remove ${p.etf_ticker}?`)) return;
    await fetch(`${API}/api/portfolio/positions/${p.etf_ticker}`, { method: 'DELETE' });
    load();
  };

  const showDetail = async (ticker) => {
    if (selectedTicker === ticker) { setSelectedTicker(null); return; }
    setSelectedTicker(ticker);
  };

  if (error) return <div className="error">Error: {error}</div>;
  if (!data) return <div className="empty">Loading...</div>;

  const totalPnlPositive = data.total_pnl_zar > 0;
  const totalPnlNegative = data.total_pnl_zar < 0;

  return (
    <div>
      <h2>Portfolio</h2>
      <div className="summary-cards">
        <SummaryCard label="Total Value" value={formatZAR(data.total_value_zar)} />
        <SummaryCard label="Total Cost" value={formatZAR(data.total_cost_zar)} />
        <SummaryCard label="P&L (ZAR)" value={formatZAR(data.total_pnl_zar)} positive={totalPnlPositive ? true : totalPnlNegative ? false : undefined} />
        <SummaryCard label="P&L (%)" value={formatPct(data.total_pnl_pct)} positive={totalPnlPositive ? true : totalPnlNegative ? false : undefined} />
      </div>

      <AddPositionForm onAdded={load} />

      {data.positions.length === 0 ? (
        <div className="empty">No positions yet. Add your first ETF above.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Name</th>
              <th>Shares</th>
              <th>Cost/Share</th>
              <th>Last Price</th>
              <th>Value (ZAR)</th>
              <th>Cost (ZAR)</th>
              <th>P&L (ZAR)</th>
              <th>P&L %</th>
              <th>Weight</th>
              <th>TER</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.positions.map((p) => (
              <React.Fragment key={p.etf_ticker}>
                <tr className={`list-item${selectedTicker === p.etf_ticker ? ' selected' : ''}`} onClick={() => showDetail(p.etf_ticker)}>
                  <td><strong>{p.etf_ticker}</strong></td>
                  <td>{p.etf_name}</td>
                  <td>{p.shares}</td>
                  <td>{formatZAR(p.cost_basis_per_share)}</td>
                  <td>{p.last_price ? formatZAR(p.last_price) : '-'}</td>
                  <td>{formatZAR(p.value_zar)}</td>
                  <td>{formatZAR(p.cost_zar)}</td>
                  <td className={p.pnl_zar > 0 ? 'positive' : p.pnl_zar < 0 ? 'negative' : ''}>{formatZAR(p.pnl_zar)}</td>
                  <td className={p.pnl_pct > 0 ? 'positive' : p.pnl_pct < 0 ? 'negative' : ''}>{formatPct(p.pnl_pct)}</td>
                  <td>{p.weight_pct}%</td>
                  <td>{p.ter}%</td>
                  <td>
                    <button className="btn-danger btn-sm" onClick={(e) => { e.stopPropagation(); removePosition(p); }}>Remove</button>
                  </td>
                </tr>
                {selectedTicker === p.etf_ticker && (
                  <tr><td colSpan={12} style={{ padding: 0 }}>
                    <PortfolioDetail ticker={p.etf_ticker} shares={p.shares} />
                  </td></tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── PortfolioDetail ─────────────────────────────────────────────────────────
function PortfolioDetail({ ticker, shares }) {
  const [etf, setEtf] = React.useState(null);

  React.useEffect(() => {
    fetch(`${API}/api/etf/${ticker}`).then((r) => r.json()).then(setEtf);
  }, [ticker]);

  if (!etf) return <div style={{ padding: 16 }}>Loading...</div>;

  return (
    <div style={{ padding: 16, background: 'var(--bg-secondary)' }}>
      <h4 style={{ marginBottom: 8 }}>{etf.name}</h4>
      <div style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 12 }}>
        Benchmark: {etf.benchmark} · TER: {etf.ter}% · {etf.holdings?.length || 0} holdings
      </div>
      {etf.holdings?.length > 0 ? (
        <table className="data-table">
          <thead>
            <tr><th>Ticker</th><th>Name</th><th>Weight</th><th>Sector</th></tr>
          </thead>
          <tbody>
            {etf.holdings.map((h) => (
              <tr key={h.ticker}>
                <td><strong>{h.ticker}</strong></td>
                <td>{h.name}</td>
                <td>{formatPct(h.weight)}</td>
                <td>{h.sector}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="empty" style={{ padding: 16 }}>No holdings data. Run refresh to populate.</div>
      )}
    </div>
  );
}

// ── HoldingsRollup ──────────────────────────────────────────────────────────
function HoldingsRollup() {
  const [data, setData] = React.useState(null);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    fetch(`${API}/api/portfolio/rollup`)
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error">Error: {error}</div>;
  if (!data) return <div className="empty">Loading...</div>;

  const sectors = Object.entries(data.sector_allocation || {});

  return (
    <div>
      <h2>Consolidated Holdings</h2>

      {sectors.length > 0 && (
        <>
          <h3>Sector Allocation</h3>
          <div className="sector-tags">
            {sectors.map(([sector, pct]) => (
              <span key={sector} className="sector-tag">{sector}: {formatPct(pct)}</span>
            ))}
          </div>
        </>
      )}

      {data.top_10?.length > 0 && (
        <>
          <h3>Top 10 Holdings</h3>
          <table className="data-table">
            <thead>
              <tr><th>Ticker</th><th>Name</th><th>Weight</th><th>Sector</th><th>Via ETFs</th></tr>
            </thead>
            <tbody>
              {data.top_10.map((h) => (
                <tr key={h.ticker}>
                  <td><strong>{h.ticker}</strong></td>
                  <td>{h.name}</td>
                  <td>{formatPct(h.total_weight_pct)}</td>
                  <td>{h.sector}</td>
                  <td style={{ fontSize: 11 }}>
                    {h.via_etfs.map((v) => `${v.etf_ticker} (${formatPct(v.weight_pct)})`).join(', ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {data.consolidated_holdings?.length > 0 && (
        <>
          <h3>All Consolidated Holdings ({data.consolidated_holdings.length})</h3>
          <table className="data-table">
            <thead>
              <tr><th>Ticker</th><th>Name</th><th>Weight</th><th>Sector</th><th>Via</th></tr>
            </thead>
            <tbody>
              {data.consolidated_holdings.map((h) => (
                <tr key={h.ticker}>
                  <td><strong>{h.ticker}</strong></td>
                  <td>{h.name}</td>
                  <td>{formatPct(h.total_weight_pct)}</td>
                  <td>{h.sector}</td>
                  <td>{h.via_etfs.map((v) => v.etf_ticker).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {!data.consolidated_holdings?.length && <div className="empty">Add positions with holdings data to see consolidated view.</div>}
    </div>
  );
}

// ── EtfList ─────────────────────────────────────────────────────────────────
function EtfList() {
  const [etfs, setEtfs] = React.useState([]);
  const [error, setError] = React.useState(null);
  const [selected, setSelected] = React.useState(null);
  const [addingTicker, setAddingTicker] = React.useState(null);
  const [addShares, setAddShares] = React.useState('');
  const [addCost, setAddCost] = React.useState('');
  const [adding, setAdding] = React.useState(false);
  const [addError, setAddError] = React.useState(null);
  const [addedTickers, setAddedTickers] = React.useState(new Set());

  React.useEffect(() => {
    fetch(`${API}/api/etf`)
      .then((r) => r.json())
      .then((d) => setEtfs(d.etfs));
  }, []);

  if (error) return <div className="error">Error: {error}</div>;

  const showDetail = async (ticker) => {
    if (selected?.ticker === ticker) { setSelected(null); return; }
    const res = await fetch(`${API}/api/etf/${ticker}`);
    setSelected(await res.json());
  };

  const startAdd = (ev, ticker) => {
    ev.stopPropagation();
    setAddingTicker(ticker);
    setAddShares('');
    setAddCost('');
    setAddError(null);
  };

  const cancelAdd = (ev) => {
    ev.stopPropagation();
    setAddingTicker(null);
  };

  const confirmAdd = async (ev, ticker) => {
    ev.stopPropagation();
    const shares = parseFloat(addShares);
    if (!shares || shares <= 0) {
      setAddError('Enter a valid number of shares');
      return;
    }
    setAdding(true);
    setAddError(null);
    try {
      const res = await fetch(`${API}/api/portfolio/positions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          etf_ticker: ticker,
          shares: shares,
          cost_basis_per_share: parseFloat(addCost) || 0,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setAddedTickers(prev => new Set(prev).add(ticker));
      setAddingTicker(null);
      setTimeout(() => setAddedTickers(prev => { const n = new Set(prev); n.delete(ticker); return n; }), 2000);
    } catch (err) {
      setAddError(err.message);
    } finally {
      setAdding(false);
    }
  };

  return (
    <div>
      <h2>ETFs</h2>
      {etfs.length === 0 ? (
        <div className="empty">No ETFs configured.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr><th>Ticker</th><th>Name</th><th>Benchmark</th><th>TER</th><th>Holdings</th><th style={{ width: 140 }}>Action</th></tr>
          </thead>
          <tbody>
            {etfs.map((e) => (
              <React.Fragment key={e.ticker}>
                <tr className={`list-item${selected?.ticker === e.ticker ? ' selected' : ''}`} onClick={() => showDetail(e.ticker)}>
                  <td><strong>{e.ticker}</strong></td>
                  <td>{e.name}</td>
                  <td className="subtitle">{e.benchmark}</td>
                  <td>{e.ter}%</td>
                  <td>{e.holding_count}</td>
                  <td>
                    {addingTicker === e.ticker ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '4px 0' }} onClick={(ev) => ev.stopPropagation()}>
                        <input type="number" step="any" value={addShares} onChange={(ev) => setAddShares(ev.target.value)} placeholder="Shares" style={{ width: 80, padding: '2px 6px', fontSize: 11, background: 'var(--bg-input)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text-primary)' }} />
                        <input type="number" step="any" value={addCost} onChange={(ev) => setAddCost(ev.target.value)} placeholder="Cost/share" style={{ width: 80, padding: '2px 6px', fontSize: 11, background: 'var(--bg-input)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text-primary)' }} />
                        {addError && <span style={{ color: 'var(--red)', fontSize: 10 }}>{addError}</span>}
                        <div style={{ display: 'flex', gap: 4 }}>
                          <button className="btn-primary btn-sm" disabled={adding} onClick={(ev) => confirmAdd(ev, e.ticker)}>{adding ? '...' : 'Add'}</button>
                          <button className="btn-danger btn-sm" onClick={(ev) => cancelAdd(ev)}>Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <button className="btn-primary btn-sm" onClick={(ev) => startAdd(ev, e.ticker)}>
                        {addedTickers.has(e.ticker) ? '✓ Added' : '+ Portfolio'}
                      </button>
                    )}
                  </td>
                </tr>
                {selected?.ticker === e.ticker && (
                  <tr><td colSpan={6} style={{ padding: 0 }}>
                    <EtfDetail etf={selected} />
                  </td></tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── EtfDetail ───────────────────────────────────────────────────────────────
function EtfDetail({ etf }) {
  return (
    <div style={{ padding: 16, background: 'var(--bg-card)', borderTop: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <h4>{etf.name}</h4>
        {etf.current_price && <span className="summary-value" style={{ fontSize: 16 }}>{formatZAR(etf.current_price)}</span>}
      </div>
      <div style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 12 }}>
        Benchmark: {etf.benchmark} · TER: {etf.ter}% · {etf.holding_count || etf.holdings?.length || 0} holdings
      </div>
      {etf.holdings?.length > 0 ? (
        <table className="data-table">
          <thead><tr><th>Ticker</th><th>Name</th><th>Weight</th><th>Sector</th></tr></thead>
          <tbody>
            {etf.holdings.map((h) => (
              <tr key={h.ticker}><td><strong>{h.ticker}</strong></td><td>{h.name}</td><td>{formatPct(h.weight)}</td><td>{h.sector}</td></tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="empty" style={{ padding: 16 }}>No holdings data available.</div>
      )}
    </div>
  );
}

// ── Error Boundary ──────────────────────────────────────────────────────────
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, fontFamily: 'monospace', background: '#0f1f2a', color: '#ef4444', minHeight: '100vh' }}>
          <h2 style={{ color: '#ef4444' }}>⚠️ ETF Tracker — Render Error</h2>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, marginTop: 16 }}>
            {this.state.error.stack || this.state.error.message || String(this.state.error)}
          </pre>
          <button onClick={() => window.location.reload()} style={{ marginTop: 16, padding: '8px 16px', background: '#334155', color: '#f1f6f9', border: '1px solid #475669', borderRadius: 4, cursor: 'pointer' }}>
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── App ─────────────────────────────────────────────────────────────────────
function App() {
  const [tab, setTab] = React.useState('portfolio');

  return (
    <div className="app">
      <div className="header">
        <h1>ETF Tracker</h1>
        <div className="nav">
          <button className={tab === 'portfolio' ? 'active' : ''} onClick={() => setTab('portfolio')}>Portfolio</button>
          <button className={tab === 'holdings' ? 'active' : ''} onClick={() => setTab('holdings')}>Holdings</button>
          <button className={tab === 'etfs' ? 'active' : ''} onClick={() => setTab('etfs')}>ETFs</button>
          <ThemeToggle />
        </div>
      </div>

      {tab === 'portfolio' && <PortfolioPage />}
      {tab === 'holdings' && <HoldingsRollup />}
      {tab === 'etfs' && <EtfList />}
    </div>
  );
}

// ── Mount ───────────────────────────────────────────────────────────────────
createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </ErrorBoundary>
);

export default App;
