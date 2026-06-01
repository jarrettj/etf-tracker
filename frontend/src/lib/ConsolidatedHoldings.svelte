<script>
	import { onMount } from 'svelte';
	import { formatPct } from '$lib/utils.js';
	import { api } from '$lib/api.js';

	let data = $state(null);
	let error = $state(null);
	let loading = $state(true);

	onMount(async () => {
		try {
			data = await api.portfolioRollup();
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	});

	let sectors = $derived(Object.entries(data?.sector_allocation || {}));
</script>

{#if error}
	<div class="error">Error: {error}</div>
{:else if loading}
	<div class="empty">Loading...</div>
{:else if data}
	<h2>Consolidated Holdings</h2>

	{#if sectors.length > 0}
		<h3>Sector Allocation</h3>
		<div class="sector-tags">
			{#each sectors as [sector, pct]}
				<span class="sector-tag">{sector}: {formatPct(pct)}</span>
			{/each}
		</div>
	{/if}

	{#if data.top_10?.length > 0}
		<h3>Top 10 Holdings</h3>
		<table class="data-table">
			<thead>
				<tr><th>Ticker</th><th>Name</th><th>Weight</th><th>Sector</th><th>Via ETFs</th></tr>
			</thead>
			<tbody>
				{#each data.top_10 as h}
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

	{#if data.consolidated_holdings?.length > 0}
		<h3>All Consolidated Holdings ({data.consolidated_holdings.length})</h3>
		<table class="data-table">
			<thead>
				<tr><th>Ticker</th><th>Name</th><th>Weight</th><th>Sector</th><th>Via</th></tr>
			</thead>
			<tbody>
				{#each data.consolidated_holdings as h}
					<tr>
						<td><strong>{h.ticker}</strong></td>
						<td>{h.name}</td>
						<td>{formatPct(h.total_weight_pct)}</td>
						<td>{h.sector}</td>
						<td style="color:var(--text-muted)">
							{h.via_etfs.map(v => v.etf_ticker).join(', ')}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}

	{#if !data.consolidated_holdings?.length}
		<div class="empty">Add positions with holdings data to see consolidated view.</div>
	{/if}
{/if}
