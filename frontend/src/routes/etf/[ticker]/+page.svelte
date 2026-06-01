<script>
	import { onMount } from 'svelte';
	import { formatZAR, formatPct } from '$lib/utils.js';
	import { api } from '$lib/api.js';

	// SvelteKit sets the param via the load function pattern,
	// but for simplicity we read it from the URL on mount.
	let ticker = $state('');
	let etf = $state(null);
	let loading = $state(true);
	let error = $state(null);

	onMount(async () => {
		// Extract ticker from URL path: /etf/STXESG
		const parts = window.location.pathname.split('/').filter(Boolean);
		const t = (parts[1] || '').toUpperCase();
		ticker = t;
		if (!t) { loading = false; return; }
		loading = true;
		error = null;
		try {
			etf = await api.etfDetail(t);
		} catch (e) {
			error = e.message || String(e);
		} finally {
			loading = false;
		}
	});
</script>

<div class="app">
	<header class="header">
		<h1><a href="/" style="text-decoration:none;color:inherit">🇿🇦 ETF Tracker</a></h1>
	</header>

	<main class="content">
		{#if error}
			<div class="error">Error: {error}</div>
		{:else if loading}
			<div class="empty">Loading {ticker}…</div>
		{:else if etf}
			<!-- ETF Header Card -->
			<div class="etf-header">
				<div class="etf-header-top">
					<div>
						<h2>{etf.ticker}</h2>
						<div class="subtitle">{etf.name}</div>
					</div>
					<div class="etf-price">
						{#if etf.current_price != null && etf.current_price != undefined}
							<span class="price-value">{formatZAR(etf.current_price)}</span>
							{#if etf.price_stale}<span class="stale-badge">⚠ stale</span>{/if}
						{:else}
							<span class="subtitle">No price</span>
						{/if}
					</div>
				</div>

				<div class="etf-meta">
					<div class="meta-item">
						<span class="meta-label">Benchmark</span>
						<span>{etf.benchmark ?? '—'}</span>
					</div>
					<div class="meta-item">
						<span class="meta-label">TER</span>
						<span>{etf.ter != null ? etf.ter + '%' : '—'}</span>
					</div>
					<div class="meta-item">
						<span class="meta-label">Holdings</span>
						<span>{etf.holding_count ?? etf.holdings?.length ?? 0}</span>
					</div>
					<div class="meta-item">
						<span class="meta-label">Refreshed</span>
						<span class="subtitle">{etf.last_refreshed ? etf.last_refreshed.slice(0, 10) : '—'}</span>
					</div>
				</div>
			</div>

			<!-- Holdings Table -->
			{#if etf.holdings?.length > 0}
				<h3>Top Holdings ({etf.holdings.length})</h3>
				<table class="data-table">
					<thead>
						<tr>
							<th>#</th>
							<th>Ticker</th>
							<th>Name</th>
							<th style="text-align:right">Weight</th>
							<th>Sector</th>
						</tr>
					</thead>
					<tbody>
						{#each etf.holdings as h, i}
							<tr>
								<td class="subtitle">{i + 1}</td>
								<td><strong>{h.ticker}</strong></td>
								<td>{h.name}</td>
								<td style="text-align:right">{formatPct(h.weight)}</td>
								<td>{h.sector ?? '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{:else}
				<div class="empty">No holdings data available.</div>
			{/if}

			<div class="actions" style="margin-top:24px">
				<a href="/" class="btn-primary" style="text-decoration:none;display:inline-block">← Back</a>
			</div>
		{/if}
	</main>
</div>

<style>
	.etf-header {
		background: var(--bg-card);
		border-radius: 10px;
		padding: 20px;
		margin-bottom: 20px;
	}
	.etf-header-top {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 16px;
	}
	.etf-header h2 { margin: 0; font-size: 28px; }
	.etf-price { text-align: right; }
	.price-value { font-size: 24px; font-weight: 700; }
	.etf-meta {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: 12px;
		padding-top: 16px;
		border-top: 1px solid var(--border);
	}
	.meta-item { display: flex; flex-direction: column; gap: 2px; }
	.meta-label {
		font-size: 11px; font-weight: 600;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	h3 { margin: 20px 0 12px; font-size: 16px; }
</style>
