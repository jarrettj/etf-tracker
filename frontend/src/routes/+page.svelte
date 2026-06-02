<script>
	import { onMount } from 'svelte';
	import { getInitialTheme, applyTheme, formatZAR, formatPct, sortRows, filterRows, toCsv, downloadCsv } from '$lib/utils.js';
	import { api } from '$lib/api.js';

	// Inline sub-components
	import PortfolioDetail from '$lib/PortfolioDetail.svelte';
	import EtfDetail from '$lib/EtfDetail.svelte';

	const tabs = [
		{ id: 'portfolio', label: 'Portfolio' },
		{ id: 'etfs', label: 'ETFs' },
		{ id: 'holdings', label: 'Consolidated' },
		{ id: 'status', label: 'Status' },
	];

	let activeTab = $state('portfolio');
	let theme = $state('dark');

	// ── Portfolio state ──
	let portfolioData = $state(null);
	let portfolioError = $state(null);
	let portfolioLoading = $state(true);
	let selectedTicker = $state(null);
	let addTicker = $state('');
	let addShares = $state('');
	let addCost = $state('');
	let adding = $state(false);
	let addError = $state(null);

	// ── Edit position state ──
	let editTicker = $state(null);
	let editShares = $state('');
	let editCost = $state('');
	let editing = $state(false);
	let editError = $state(null);

	// ── Table sort/filter state ──
	let portfolioFilter = $state('');
	let portfolioSort = $state({ key: 'value_zar', dir: 'desc' });
	let etfFilter = $state('');
	let etfSort = $state({ key: 'ticker', dir: 'asc' });
	let holdingsFilter = $state('');
	let holdingsSort = $state({ key: 'total_weight_pct', dir: 'desc' });

	// ── ETF list state ──
	let etfs = $state([]);
	let etfsLoading = $state(true);
	let etfsError = $state(null);
	let selectedEtf = $state(null);
	let addRowTicker = $state(null);
	let addRowShares = $state('');
	let addRowCost = $state('');
	let addingToPortfolio = $state(false);
	let addRowError = $state(null);
	let justAdded = $state(new Set());

	// ── Holdings state ──
	let holdingsData = $state(null);
	let holdingsLoading = $state(true);
	let holdingsError = $state(null);

	// ── Status state ──
	let statusMeta = $state(null);
	let statusHealth = $state(null);
	let statusScrape = $state(null);
	let statusLoading = $state(true);
	let statusError = $state(null);
	let refreshing = $state(false);
	let refreshingPrices = $state(false);

	onMount(() => {
		theme = getInitialTheme();
		applyTheme(theme);
		loadPortfolio();
		loadEtfs();
		loadHoldings();
		loadStatus();
	});

	function toggleTheme() {
		theme = theme === 'dark' ? 'light' : 'dark';
		applyTheme(theme);
	}

	function setTab(id) {
		activeTab = id;
	}

	// ── Portfolio functions ──
	async function loadPortfolio() {
		portfolioLoading = true;
		portfolioError = null;
		try {
			portfolioData = await api.portfolio();
		} catch (e) {
			portfolioError = e.message;
		} finally {
			portfolioLoading = false;
		}
	}

	async function addPosition() {
		const ticker = addTicker.trim().toUpperCase();
		const shares = parseFloat(addShares);
		const cost = parseFloat(addCost) || 0;
		if (!ticker || !shares || shares <= 0) {
			addError = 'Enter ticker and shares';
			return;
		}
		adding = true;
		addError = null;
		try {
			await api.addPosition({ etf_ticker: ticker, shares, cost_basis_per_share: cost });
			addTicker = '';
			addShares = '';
			addCost = '';
			await loadPortfolio();
		} catch (e) {
			addError = e.message;
		} finally {
			adding = false;
		}
	}

	async function removePosition(p) {
		if (!confirm(`Remove ${p.etf_ticker} from portfolio?`)) return;
		await api.removePosition(p.etf_ticker);
		if (selectedTicker === p.etf_ticker) selectedTicker = null;
		await loadPortfolio();
	}

	function toggleDetail(ticker) {
		if (editTicker) return; // don't collapse the row while editing
		selectedTicker = selectedTicker === ticker ? null : ticker;
	}

	function startEdit(ev, p) {
		ev.stopPropagation();
		editTicker = p.etf_ticker;
		editShares = String(p.shares);
		editCost = String(p.cost_basis_per_share);
		editError = null;
	}

	function cancelEdit(ev) {
		if (ev) ev.stopPropagation();
		editTicker = null;
		editError = null;
	}

	async function saveEdit(ev, ticker) {
		ev.stopPropagation();
		const shares = parseFloat(editShares);
		const cost = parseFloat(editCost) || 0;
		if (!shares || shares <= 0) {
			editError = 'Enter valid shares';
			return;
		}
		editing = true;
		editError = null;
		try {
			await api.updatePosition(ticker, { shares, cost_basis_per_share: cost });
			editTicker = null;
			await loadPortfolio();
			await loadHoldings();
		} catch (e) {
			editError = e.message;
		} finally {
			editing = false;
		}
	}

	// ── Sorting helper ──
	function toggleSort(sortState, key) {
		if (sortState.key === key) {
			sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
		} else {
			sortState.key = key;
			sortState.dir = 'asc';
		}
	}

	function sortIndicator(sortState, key) {
		if (sortState.key !== key) return '';
		return sortState.dir === 'asc' ? ' ▲' : ' ▼';
	}

	let totalPnlPos = $derived(portfolioData?.total_pnl_zar > 0);
	let totalPnlNeg = $derived(portfolioData?.total_pnl_zar < 0);

	let visiblePositions = $derived(
		sortRows(
			filterRows(portfolioData?.positions || [], portfolioFilter, ['etf_ticker', 'etf_name']),
			portfolioSort.key,
			portfolioSort.dir
		)
	);

	function exportPortfolioCsv() {
		const cols = [
			{ key: 'etf_ticker', label: 'Ticker' },
			{ key: 'etf_name', label: 'Name' },
			{ key: 'shares', label: 'Shares' },
			{ key: 'cost_basis_per_share', label: 'Cost/Share' },
			{ key: 'last_price', label: 'Last Price' },
			{ key: 'value_zar', label: 'Value (ZAR)' },
			{ key: 'cost_zar', label: 'Cost (ZAR)' },
			{ key: 'pnl_zar', label: 'P&L (ZAR)' },
			{ key: 'pnl_pct', label: 'P&L %' },
			{ key: 'weight_pct', label: 'Weight %' },
			{ key: 'ter', label: 'TER' },
		];
		downloadCsv('portfolio.csv', toCsv(visiblePositions, cols));
	}

	// ── ETF functions ──
	async function loadEtfs() {
		etfsLoading = true;
		try {
			const d = await api.listEtfs();
			etfs = d.etfs || [];
		} catch (e) {
			etfsError = e.message;
		} finally {
			etfsLoading = false;
		}
	}

	async function showEtfDetail(e) {
		if (selectedEtf?.ticker === e.ticker) {
			selectedEtf = null;
		} else {
			selectedEtf = await api.etfDetail(e.ticker);
		}
	}

	function startAddToPortfolio(ev, ticker) {
		ev.stopPropagation();
		addRowTicker = ticker;
		addRowShares = '';
		addRowCost = '';
		addRowError = null;
	}

	function cancelAddToPortfolio(ev) {
		ev.stopPropagation();
		addRowTicker = null;
	}

	async function confirmAddToPortfolio(ev, ticker) {
		ev.stopPropagation();
		const shares = parseFloat(addRowShares);
		if (!shares || shares <= 0) {
			addRowError = 'Enter valid shares';
			return;
		}
		addingToPortfolio = true;
		addRowError = null;
		try {
			await api.addPosition({ etf_ticker: ticker, shares, cost_basis_per_share: parseFloat(addRowCost) || 0 });
			justAdded = new Set([...justAdded, ticker]);
			addRowTicker = null;
			setTimeout(() => {
				justAdded = new Set([...justAdded].filter(t => t !== ticker));
			}, 2000);
			await loadPortfolio();
		} catch (e) {
			addRowError = e.message;
		} finally {
			addingToPortfolio = false;
		}
	}

	// ── Holdings functions ──
	async function loadHoldings() {
		holdingsLoading = true;
		try {
			holdingsData = await api.portfolioRollup();
		} catch (e) {
			holdingsError = e.message;
		} finally {
			holdingsLoading = false;
		}
	}

	let sectors = $derived(Object.entries(holdingsData?.sector_allocation || {}));
	let maxSectorPct = $derived(sectors.length ? Math.max(...sectors.map(([, p]) => p)) : 0);

	let visibleEtfs = $derived(
		sortRows(filterRows(etfs, etfFilter, ['ticker', 'name', 'benchmark']), etfSort.key, etfSort.dir)
	);

	let visibleHoldings = $derived(
		sortRows(
			filterRows(holdingsData?.consolidated_holdings || [], holdingsFilter, ['ticker', 'name', 'sector']),
			holdingsSort.key,
			holdingsSort.dir
		)
	);

	function exportHoldingsCsv() {
		const rows = (holdingsData?.consolidated_holdings || []).map((h) => ({
			ticker: h.ticker,
			name: h.name,
			total_weight_pct: h.total_weight_pct,
			sector: h.sector,
			via_etfs: h.via_etfs.map((v) => v.etf_ticker).join(' '),
		}));
		const cols = [
			{ key: 'ticker', label: 'Ticker' },
			{ key: 'name', label: 'Name' },
			{ key: 'total_weight_pct', label: 'Weight %' },
			{ key: 'sector', label: 'Sector' },
			{ key: 'via_etfs', label: 'Via ETFs' },
		];
		downloadCsv('consolidated_holdings.csv', toCsv(rows, cols));
	}

	// ── Status functions ──
	async function loadStatus() {
		statusLoading = true;
		try {
			const [m, h, s] = await Promise.all([api.statusMeta(), api.health(), api.statusScrape()]);
			statusMeta = m;
			statusHealth = h;
			statusScrape = s;
		} catch (e) {
			statusError = e.message;
		} finally {
			statusLoading = false;
		}
	}

	async function refreshCache() {
		refreshing = true;
		try {
			await api.invalidateCache();
			await loadStatus();
		} catch (e) {
			statusError = e.message;
		} finally {
			refreshing = false;
		}
	}

	async function refreshPrices() {
		refreshingPrices = true;
		try {
			await api.refreshPrices();
			await Promise.all([loadPortfolio(), loadHoldings()]);
		} catch (e) {
			statusError = e.message;
		} finally {
			refreshingPrices = false;
		}
	}

	function fmtTime(ts) {
		if (!ts) return '-';
		const d = new Date(ts);
		return isNaN(d.getTime()) ? ts : d.toLocaleString();
	}
</script>

<div class="app">
	<header class="header">
		<h1>🇿🇦 ETF Tracker</h1>
		<nav class="nav">
			{#each tabs as tab}
				<button class:active={activeTab === tab.id} onclick={() => setTab(tab.id)}>
					{tab.label}
				</button>
			{/each}
		</nav>
		<button class="theme-toggle" onclick={toggleTheme} title="Switch to {theme === 'dark' ? 'light' : 'dark'} mode">
			{theme === 'dark' ? '☀️' : '🌙'}
		</button>
	</header>

	<main class="content">
		<!-- ═══ PORTFOLIO TAB ═══ -->
		<div style:display={activeTab === 'portfolio' ? 'block' : 'none'}>
			{#if portfolioError}
				<div class="error">Error: {portfolioError}</div>
			{:else if portfolioLoading}
				<div class="empty">Loading portfolio...</div>
			{:else}
				<h2>Portfolio</h2>

				<div class="summary-cards">
					<div class="summary-card">
						<div class="summary-label">Total Value</div>
						<div class="summary-value">{formatZAR(portfolioData.total_value_zar)}</div>
					</div>
					<div class="summary-card">
						<div class="summary-label">Total Cost</div>
						<div class="summary-value">{formatZAR(portfolioData.total_cost_zar)}</div>
					</div>
					<div class="summary-card">
						<div class="summary-label">P&L (ZAR)</div>
						<div class="summary-value" class:positive={totalPnlPos} class:negative={totalPnlNeg}>
							{formatZAR(portfolioData.total_pnl_zar)}
						</div>
					</div>
					<div class="summary-card">
						<div class="summary-label">P&L (%)</div>
						<div class="summary-value" class:positive={totalPnlPos} class:negative={totalPnlNeg}>
							{formatPct(portfolioData.total_pnl_pct)}
						</div>
					</div>
				</div>

				<div class="add-form">
					<h3>Add Position</h3>
					{#if addError}
						<div class="error" style="margin-bottom:8px;padding:8px 12px;font-size:12px">{addError}</div>
					{/if}
					<div class="form-row">
						<input bind:value={addTicker} placeholder="Ticker (e.g. STXNDQ)" />
						<input type="number" step="any" bind:value={addShares} placeholder="Shares" />
						<input type="number" step="any" bind:value={addCost} placeholder="Cost basis / share (ZAR)" />
						<button class="btn-primary" disabled={adding || !addTicker.trim() || !addShares} onclick={addPosition}>
							{adding ? 'Adding...' : 'Add'}
						</button>
					</div>
				</div>

				{#if portfolioData.positions.length === 0}
					<div class="empty">No positions yet. Add your first ETF above.</div>
				{:else}
					<div class="table-toolbar">
						<input class="filter-input" bind:value={portfolioFilter} placeholder="Filter by ticker or name..." />
						<button class="btn-secondary btn-sm" onclick={exportPortfolioCsv}>Export CSV</button>
					</div>
					<table class="data-table">
						<thead>
							<tr>
								<th onclick={() => toggleSort(portfolioSort, 'etf_ticker')} style="cursor:pointer">Ticker{sortIndicator(portfolioSort, 'etf_ticker')}</th>
								<th onclick={() => toggleSort(portfolioSort, 'etf_name')} style="cursor:pointer">Name{sortIndicator(portfolioSort, 'etf_name')}</th>
								<th onclick={() => toggleSort(portfolioSort, 'shares')} style="cursor:pointer">Shares{sortIndicator(portfolioSort, 'shares')}</th>
								<th onclick={() => toggleSort(portfolioSort, 'cost_basis_per_share')} style="cursor:pointer">Cost/Share{sortIndicator(portfolioSort, 'cost_basis_per_share')}</th>
								<th onclick={() => toggleSort(portfolioSort, 'last_price')} style="cursor:pointer">Last Price{sortIndicator(portfolioSort, 'last_price')}</th>
								<th onclick={() => toggleSort(portfolioSort, 'value_zar')} style="cursor:pointer">Value (ZAR){sortIndicator(portfolioSort, 'value_zar')}</th>
								<th onclick={() => toggleSort(portfolioSort, 'cost_zar')} style="cursor:pointer">Cost (ZAR){sortIndicator(portfolioSort, 'cost_zar')}</th>
								<th onclick={() => toggleSort(portfolioSort, 'pnl_zar')} style="cursor:pointer">P&L (ZAR){sortIndicator(portfolioSort, 'pnl_zar')}</th>
								<th onclick={() => toggleSort(portfolioSort, 'pnl_pct')} style="cursor:pointer">P&L %{sortIndicator(portfolioSort, 'pnl_pct')}</th>
								<th onclick={() => toggleSort(portfolioSort, 'weight_pct')} style="cursor:pointer">Weight{sortIndicator(portfolioSort, 'weight_pct')}</th>
								<th onclick={() => toggleSort(portfolioSort, 'ter')} style="cursor:pointer">TER{sortIndicator(portfolioSort, 'ter')}</th>
								<th style="width:130px"></th>
							</tr>
						</thead>
						<tbody>
							{#each visiblePositions as p}
								<tr class:selected={selectedTicker === p.etf_ticker} onclick={() => toggleDetail(p.etf_ticker)} style="cursor:pointer">
									<td><strong>{p.etf_ticker}</strong></td>
									<td>{p.etf_name}</td>
									{#if editTicker === p.etf_ticker}
										<td onclick={(ev) => ev.stopPropagation()}><input type="number" step="any" bind:value={editShares} style="width:80px" /></td>
										<td onclick={(ev) => ev.stopPropagation()}><input type="number" step="any" bind:value={editCost} style="width:90px" /></td>
									{:else}
										<td>{p.shares}</td>
										<td>{formatZAR(p.cost_basis_per_share)}</td>
									{/if}
									<td>
										{#if p.last_price != null}
											{formatZAR(p.last_price)}
											{#if p.price_stale}<span class="stale-badge">⚠ stale</span>{/if}
										{:else}-{/if}
									</td>
									<td>{formatZAR(p.value_zar)}</td>
									<td>{formatZAR(p.cost_zar)}</td>
									<td class:positive={p.pnl_zar > 0} class:negative={p.pnl_zar < 0}>{formatZAR(p.pnl_zar)}</td>
									<td class:positive={p.pnl_pct > 0} class:negative={p.pnl_pct < 0}>{formatPct(p.pnl_pct)}</td>
									<td>{p.weight_pct}%</td>
									<td>{p.ter}%</td>
									<td>
										{#if editTicker === p.etf_ticker}
											<div style="display:flex;gap:4px" onclick={(ev) => ev.stopPropagation()}>
												<button class="btn-primary btn-sm" disabled={editing} onclick={(ev) => saveEdit(ev, p.etf_ticker)}>{editing ? '...' : 'Save'}</button>
												<button class="btn-secondary btn-sm" onclick={cancelEdit}>Cancel</button>
											</div>
											{#if editError}<span style="color:var(--red);font-size:10px">{editError}</span>{/if}
										{:else}
											<div style="display:flex;gap:4px">
												<button class="btn-secondary btn-sm" onclick={(ev) => startEdit(ev, p)}>Edit</button>
												<button class="btn-danger btn-sm" onclick={(e) => { e.stopPropagation(); removePosition(p); }}>Remove</button>
											</div>
										{/if}
									</td>
								</tr>
								{#if selectedTicker === p.etf_ticker}
									<tr><td colspan="12" style="padding:0">
										<PortfolioDetail ticker={p.etf_ticker} shares={p.shares} />
									</td></tr>
								{/if}
							{/each}
						</tbody>
					</table>

					{#if holdingsData?.top_10?.length > 0}
						<h3 style="margin-top:24px">Top Holdings (look-through)</h3>
						<table class="data-table">
							<thead><tr><th>Ticker</th><th>Name</th><th>Weight</th><th>Sector</th></tr></thead>
							<tbody>
								{#each holdingsData.top_10 as h}
									<tr>
										<td><strong>{h.ticker}</strong></td>
										<td>{h.name}</td>
										<td>{formatPct(h.total_weight_pct)}</td>
										<td>{h.sector}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					{/if}
				{/if}
			{/if}
		</div>

		<!-- ═══ ETFs TAB ═══ -->
		<div style:display={activeTab === 'etfs' ? 'block' : 'none'}>
			{#if etfsError}
				<div class="error">Error: {etfsError}</div>
			{:else if etfsLoading}
				<div class="empty">Loading ETFs...</div>
			{:else}
				<h2>ETFs</h2>
				{#if etfs.length === 0}
					<div class="empty">No ETFs configured.</div>
				{:else}
					<div class="table-toolbar">
						<input class="filter-input" bind:value={etfFilter} placeholder="Filter by ticker, name or benchmark..." />
					</div>
					<table class="data-table">
						<thead>
							<tr>
								<th onclick={() => toggleSort(etfSort, 'ticker')} style="cursor:pointer">Ticker{sortIndicator(etfSort, 'ticker')}</th>
								<th onclick={() => toggleSort(etfSort, 'name')} style="cursor:pointer">Name{sortIndicator(etfSort, 'name')}</th>
								<th onclick={() => toggleSort(etfSort, 'benchmark')} style="cursor:pointer">Benchmark{sortIndicator(etfSort, 'benchmark')}</th>
								<th onclick={() => toggleSort(etfSort, 'ter')} style="cursor:pointer">TER{sortIndicator(etfSort, 'ter')}</th>
								<th onclick={() => toggleSort(etfSort, 'holding_count')} style="cursor:pointer">Holdings{sortIndicator(etfSort, 'holding_count')}</th>
								<th style="width:160px">Action</th>
							</tr>
						</thead>
						<tbody>
							{#each visibleEtfs as e}
								<tr class:selected={selectedEtf?.ticker === e.ticker} onclick={() => showEtfDetail(e)} style="cursor:pointer">
									<td><strong><a href="/etf/{e.ticker}" onclick={(ev) => ev.stopPropagation()} style="text-decoration:none;color:inherit">{e.ticker}</a></strong></td>
									<td>{e.name}</td>
									<td class="subtitle">{e.benchmark}</td>
									<td>{e.ter != null ? e.ter + '%' : '-'}</td>
									<td>{e.holding_count}</td>
									<td>
										{#if addRowTicker === e.ticker}
											<div style="display:flex;flex-direction:column;gap:4px" onclick={(ev) => ev.stopPropagation()}>
												<input type="number" step="any" bind:value={addRowShares} placeholder="Shares" />
												<input type="number" step="any" bind:value={addRowCost} placeholder="Cost/share" />
												{#if addRowError}<span style="color:var(--red);font-size:10px">{addRowError}</span>{/if}
												<div style="display:flex;gap:4px">
													<button class="btn-primary btn-sm" disabled={addingToPortfolio} onclick={(ev) => confirmAddToPortfolio(ev, e.ticker)}>
														{addingToPortfolio ? '...' : 'Add'}
													</button>
													<button class="btn-danger btn-sm" onclick={(ev) => cancelAddToPortfolio(ev)}>Cancel</button>
												</div>
											</div>
										{:else}
											<button class="btn-primary btn-sm" onclick={(ev) => startAddToPortfolio(ev, e.ticker)}>
												{justAdded.has(e.ticker) ? '✓ Added' : '+ Portfolio'}
											</button>
										{/if}
									</td>
								</tr>
								{#if selectedEtf?.ticker === e.ticker}
									<tr><td colspan="6" style="padding:0"><EtfDetail etf={selectedEtf} /></td></tr>
								{/if}
							{/each}
						</tbody>
					</table>
				{/if}
			{/if}
		</div>

		<!-- ═══ CONSOLIDATED HOLDINGS TAB ═══ -->
		<div style:display={activeTab === 'holdings' ? 'block' : 'none'}>
			{#if holdingsError}
				<div class="error">Error: {holdingsError}</div>
			{:else if holdingsLoading}
				<div class="empty">Loading...</div>
			{:else if holdingsData}
				<h2>Consolidated Holdings</h2>

				{#if sectors.length > 0}
					<h3>Sector Allocation</h3>
					<div class="sector-chart">
						{#each sectors as [sector, pct]}
							<div class="sector-bar-row">
								<div class="sector-bar-label">{sector}</div>
								<div class="sector-bar-track">
									<div class="sector-bar-fill" style:width={(maxSectorPct ? (pct / maxSectorPct) * 100 : 0) + '%'}></div>
								</div>
								<div class="sector-bar-value">{formatPct(pct)}</div>
							</div>
						{/each}
					</div>
				{/if}

				{#if holdingsData.top_10?.length > 0}
					<h3>Top 10 Holdings</h3>
					<table class="data-table">
						<thead><tr><th>Ticker</th><th>Name</th><th>Weight</th><th>Sector</th><th>Via ETFs</th></tr></thead>
						<tbody>
							{#each holdingsData.top_10 as h}
								<tr>
									<td><strong>{h.ticker}</strong></td>
									<td>{h.name}</td>
									<td>{formatPct(h.total_weight_pct)}</td>
									<td>{h.sector}</td>
									<td style="font-size:11px;color:var(--text-muted)">
										{h.via_etfs.map(v => `${v.etf_ticker} (${formatPct(v.weight_pct)})`).join(', ')}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}

				{#if holdingsData.consolidated_holdings?.length > 0}
					<h3>All Consolidated Holdings ({holdingsData.consolidated_holdings.length})</h3>
					<div class="table-toolbar">
						<input class="filter-input" bind:value={holdingsFilter} placeholder="Filter by ticker, name or sector..." />
						<button class="btn-secondary btn-sm" onclick={exportHoldingsCsv}>Export CSV</button>
					</div>
					<table class="data-table">
						<thead>
							<tr>
								<th onclick={() => toggleSort(holdingsSort, 'ticker')} style="cursor:pointer">Ticker{sortIndicator(holdingsSort, 'ticker')}</th>
								<th onclick={() => toggleSort(holdingsSort, 'name')} style="cursor:pointer">Name{sortIndicator(holdingsSort, 'name')}</th>
								<th onclick={() => toggleSort(holdingsSort, 'total_weight_pct')} style="cursor:pointer">Weight{sortIndicator(holdingsSort, 'total_weight_pct')}</th>
								<th onclick={() => toggleSort(holdingsSort, 'sector')} style="cursor:pointer">Sector{sortIndicator(holdingsSort, 'sector')}</th>
								<th>Via</th>
							</tr>
						</thead>
						<tbody>
							{#each visibleHoldings as h}
								<tr>
									<td><strong>{h.ticker}</strong></td>
									<td>{h.name}</td>
									<td>{formatPct(h.total_weight_pct)}</td>
									<td>{h.sector}</td>
									<td style="color:var(--text-muted)">{h.via_etfs.map(v => v.etf_ticker).join(', ')}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}

				{#if !holdingsData.consolidated_holdings?.length}
					<div class="empty">Add positions with holdings data to see consolidated view.</div>
				{/if}
			{/if}
		</div>

		<!-- ═══ STATUS TAB ═══ -->
		<div style:display={activeTab === 'status' ? 'block' : 'none'}>
			{#if statusError}
				<div class="error">Error: {statusError}</div>
			{:else if statusLoading}
				<div class="empty">Loading status...</div>
			{:else}
				<h2>System Status</h2>
				<div class="summary-cards">
					<div class="summary-card">
						<div class="summary-label">Backend</div>
						<div class="summary-value" style="font-size:14px">{statusHealth?.status === 'ok' ? '✅ Online' : '❌ Offline'}</div>
					</div>
					<div class="summary-card">
						<div class="summary-label">ETFs</div>
						<div class="summary-value">{statusMeta?.etf_count ?? '-'}</div>
					</div>
					<div class="summary-card">
						<div class="summary-label">Source</div>
						<div class="summary-value" style="font-size:13px">{statusMeta?.source ?? '-'}</div>
					</div>
					<div class="summary-card">
						<div class="summary-label">Updated</div>
						<div class="summary-value" style="font-size:13px">{statusMeta?.updated ?? '-'}</div>
					</div>
				</div>
				<div style="margin-bottom:16px;display:flex;gap:8px;flex-wrap:wrap">
					<button class="btn-primary" disabled={refreshing} onclick={refreshCache}>
						{refreshing ? 'Refreshing...' : 'Invalidate Cache & Reload'}
					</button>
					<button class="btn-secondary" disabled={refreshingPrices} onclick={refreshPrices}>
						{refreshingPrices ? 'Refreshing Prices...' : 'Refresh Prices'}
					</button>
				</div>
				{#if statusMeta?.etfs?.length > 0}
					<h3>ETF Details</h3>
					<table class="data-table">
						<thead><tr><th>Ticker</th><th>Name</th><th>Holdings</th><th>Last Refreshed</th></tr></thead>
						<tbody>
							{#each statusMeta.etfs as e}
								<tr>
									<td><strong>{e.ticker}</strong></td>
									<td>{e.name}</td>
									<td>{e.holding_count}</td>
									<td class="subtitle">{e.last_refreshed ?? '-'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}

				<!-- ── Scrape status ── -->
				{#if statusScrape?.current_run}
					{@const run = statusScrape.current_run}
					<h3>Current Scrape Run</h3>
					<div class="subtitle" style="margin-bottom:8px">
						{run.type} · started {fmtTime(run.started_at)} · {run.tickers_done}/{run.tickers_total} done
					</div>
					<table class="data-table">
						<thead><tr><th>Ticker</th><th>Status</th><th>Source</th><th>Holdings</th><th>Error</th></tr></thead>
						<tbody>
							{#each Object.entries(run.tickers) as [ticker, t]}
								<tr>
									<td><strong>{ticker}</strong></td>
									<td>{t.status}</td>
									<td class="subtitle">{t.source ?? '-'}</td>
									<td>{t.holdings_found ?? '-'}</td>
									<td style="color:var(--red);font-size:11px">{t.error ?? ''}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}

				{#if statusScrape?.last_runs?.length > 0}
					<h3>Recent Scrape Runs</h3>
					<table class="data-table">
						<thead><tr><th>Type</th><th>Started</th><th>Finished</th><th>Succeeded</th><th>Failed</th></tr></thead>
						<tbody>
							{#each statusScrape.last_runs as run}
								<tr>
									<td>{run.type}</td>
									<td class="subtitle">{fmtTime(run.started_at)}</td>
									<td class="subtitle">{fmtTime(run.finished_at)}</td>
									<td class="positive">{run.tickers_succeeded ?? '-'}</td>
									<td class:negative={run.tickers_failed > 0}>{run.tickers_failed ?? '-'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{:else if !statusScrape?.current_run}
					<h3>Scrape Runs</h3>
					<div class="empty">No scrape runs recorded yet.</div>
				{/if}
			{/if}
		</div>
	</main>
</div>
