<script>
	import { formatZAR, formatPct } from '$lib/utils.js';
	import { api } from '$lib/api.js';

	let { etf } = $props();

	let rawText = $state(null);
	let rawError = $state(null);
	let rawLoading = $state(false);
	let showRaw = $state(false);

	async function toggleRaw() {
		if (showRaw) {
			showRaw = false;
			return;
		}
		showRaw = true;
		if (rawText !== null || rawError !== null) return;
		rawLoading = true;
		try {
			rawText = await api.etfRaw(etf.ticker);
		} catch (e) {
			rawError = e.message.includes('404')
				? 'No raw source stored for this ETF.'
				: e.message;
		} finally {
			rawLoading = false;
		}
	}
</script>

<div style="padding:16px;background:var(--bg-card);border-top:1px solid var(--border)">
	<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
		<h4>{etf.name}</h4>
		{#if etf.current_price != null}
			<span class="summary-value" style="font-size:16px">
				{formatZAR(etf.current_price)}
				{#if etf.price_stale}
					<span class="stale-badge">⚠️ stale</span>
				{/if}
			</span>
		{/if}
	</div>
	<div class="subtitle" style="margin-bottom:12px">
		Benchmark: {etf.benchmark} · TER: {etf.ter}% · {etf.holding_count || etf.holdings?.length || 0} holdings
	</div>

	<div style="margin-bottom:12px">
		<button class="btn-primary btn-sm" onclick={toggleRaw}>
			{showRaw ? 'Hide raw source' : 'View raw source'}
		</button>
	</div>
	{#if showRaw}
		{#if rawLoading}
			<div class="empty" style="margin:0 0 12px">Loading raw source...</div>
		{:else if rawError}
			<div class="empty" style="margin:0 0 12px">{rawError}</div>
		{:else}
			<pre style="max-height:300px;overflow:auto;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:12px;font-size:11px;white-space:pre-wrap;margin:0 0 12px">{rawText}</pre>
		{/if}
	{/if}

	{#if etf.holdings?.length > 0}
		<table class="data-table">
			<thead>
				<tr><th>Ticker</th><th>Name</th><th>Weight</th><th>Sector</th></tr>
			</thead>
			<tbody>
				{#each etf.holdings as h}
					<tr>
						<td><strong>{h.ticker}</strong></td>
						<td>{h.name}</td>
						<td>{formatPct(h.weight)}</td>
						<td>{h.sector}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{:else}
		<div class="empty" style="margin:0">No holdings data available.</div>
	{/if}
</div>
