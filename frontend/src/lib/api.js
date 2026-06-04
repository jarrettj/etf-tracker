const BASE = '';

async function get(path) {
	const res = await fetch(`${BASE}${path}`);
	if (!res.ok) throw new Error(`HTTP ${res.status}`);
	return res.json();
}

async function getText(path) {
	const res = await fetch(`${BASE}${path}`);
	if (!res.ok) throw new Error(`HTTP ${res.status}`);
	return res.text();
}

export const api = {
	health: () => get('/api/health'),
	listEtfs: () => get('/api/etf'),
	etfDetail: (ticker) => get(`/api/etf/${ticker}`),
	etfRaw: (ticker) => getText(`/api/etf/${ticker}/raw`),
	statusMeta: () => get('/api/etf/status/meta'),
	statusScrape: () => get('/api/status/scrape'),
	portfolio: () => get('/api/portfolio'),
	addPosition: (body) => fetch(`${BASE}/api/portfolio/positions`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	}).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
	updatePosition: (ticker, body) => fetch(`${BASE}/api/portfolio/positions/${ticker}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	}).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
	removePosition: (ticker) => fetch(`${BASE}/api/portfolio/positions/${ticker}`, {
		method: 'DELETE'
	}).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
	portfolioRollup: () => get('/api/portfolio/rollup'),
	invalidateCache: () => fetch(`${BASE}/api/refresh`, { method: 'POST' }).then(r => r.json()),
	refreshPrices: () => fetch(`${BASE}/api/refresh-prices`, { method: 'POST' }).then(r => r.json()),
};
