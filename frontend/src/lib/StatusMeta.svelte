<script>
	import { onMount } from 'svelte';
	import { api } from '$lib/api.js';

	let meta = $state(null);
	let health = $state(null);
	let loading = $state(true);
	let error = $state(null);
	let refreshing = $state(false);

	onMount(async () => {
		try {
			const [m, h] = await Promise.all([api.statusMeta(), api.health()]);
			meta = m;
			health = h;
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	});

	async function refresh() {
		refreshing = true;
		try {
			await api.invalidateCache();
			const [m, h] = await Promise.all([api.statusMeta(), api.health()]);
			meta = m;
			health = h;
		} catch (e) {
			error = e.message;
		} finally {
			refreshing = false;
		}
	}
</script>

{#if error}
	<div class="error">Error: {error}</div>
{:else if loading}
	<div class="empty">Loading status...</div>
{:else}
	<h2>System Status</h2>

	<div class="summary-cards">
		<div class="summary-card">
			<div class="summary-label">Backend</div>
			<div class="summary-value" style="font-size:14px">
				{health?.status === 'ok' ? '✅ Online' : '❌ Offline'}
			</div>
		</div>
		<div class="summary-card">
			<div class="summary-label">ETFs Configured</div>
			<div class="summary-value">{meta?.etf_count ?? '-'}</div>
		</div>
		<div class="summary-card">
			<div class="summary-label">Data Source</div>
			<div class="summary-value" style="font-size:13px">{meta?.source ?? '-'}</div>
		</div>
		<div class="summary-card">
			<div class="summary-label">Last Updated</div>
			<div class="summary-value" style="font-size:13px">{meta?.updated ?? '-'}</div>
		</div>
	</div>

	<div style="margin-bottom:16px">
		<button class="btn-primary" disabled={refreshing} onclick={refresh}>
			{refreshing ? 'Refreshing...' : 'Invalidate Cache & Reload'}
		</button>
	</div>

	{#if meta?.etfs?.length > 0}
		<h3>ETF Details</h3>
		<table class="data-table">
			<thead>
				<tr><th>Ticker</th><th>Name</th><th>Holdings</th><th>Last Refreshed</th></tr>
			</thead>
			<tbody>
				{#each meta.etfs as e}
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
{/if}
