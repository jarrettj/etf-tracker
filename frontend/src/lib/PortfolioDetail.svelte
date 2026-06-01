<script>
	import { formatZAR, formatPct } from '$lib/utils.js';
	import { api } from '$lib/api.js';

	let { ticker, shares } = $props();
	let etf = $state(null);
	let loading = $state(true);

	$effect(() => {
		if (ticker) {
			loading = true;
			api.etfDetail(ticker).then(d => { etf = d; loading = false; });
		}
	});
</script>

<div style="padding:16px;background:var(--bg-secondary)">
	{#if loading}
		<div class="empty" style="margin:0">Loading...</div>
	{:else if etf}
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
			Benchmark: {etf.benchmark} · TER: {etf.ter}% · {etf.holdings?.length || 0} holdings
		</div>

		{#if etf.holdings?.length > 0}
			<table class="data-table" style="margin:0">
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
			<div class="empty" style="margin:0">No holdings data. Run refresh to populate.</div>
		{/if}
	{/if}
</div>
