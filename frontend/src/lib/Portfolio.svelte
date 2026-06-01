<script>
	import { onMount } from 'svelte';
	import { formatZAR, formatPct } from '$lib/utils.js';
	import { api } from '$lib/api.js';
	import PortfolioDetail from './PortfolioDetail.svelte';

	let data = $state(null);
	let error = $state(null);
	let loading = $state(true);
	let selectedTicker = $state(null);

	// Add form
	let addTicker = $state('');
	let addShares = $state('');
	let addCost = $state('');
	let adding = $state(false);
	let addError = $state(null);

	onMount(load);

	async function load() {
		loading = true;
		error = null;
		try {
			data = await api.portfolio();
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
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
			await load();
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
		await load();
	}

	function toggleDetail(ticker) {
		selectedTicker = selectedTicker === ticker ? null : ticker;
	}

	let totalPnlPos = $derived(data?.total_pnl_zar > 0);
	let totalPnlNeg = $derived(data?.total_pnl_zar < 0);
</script>

{#if error}
	<div class="error">Error: {error}</div>
{:else if loading}
	<div class="empty">Loading...</div>
{:else}
	<h2>Portfolio</h2>

	<div class="summary-cards">
		<div class="summary-card">
			<div class="summary-label">Total Value</div>
			<div class="summary-value">{formatZAR(data.total_value_zar)}</div>
		</div>
		<div class="summary-card">
			<div class="summary-label">Total Cost</div>
			<div class="summary-value">{formatZAR(data.total_cost_zar)}</div>
		</div>
		<div class="summary-card">
			<div class="summary-label">P&L (ZAR)</div>
			<div class="summary-value"
				class:positive={totalPnlPos}
				class:negative={totalPnlNeg}>
				{formatZAR(data.total_pnl_zar)}
			</div>
		</div>
		<div class="summary-card">
			<div class="summary-label">P&L (%)</div>
			<div class="summary-value"
				class:positive={totalPnlPos}
				class:negative={totalPnlNeg}>
				{formatPct(data.total_pnl_pct)}
			</div>
		</div>
	</div>

	<!-- Add Position Form -->
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

	{#if data.positions.length === 0}
		<div class="empty">No positions yet. Add your first ETF above.</div>
	{:else}
		<table class="data-table">
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
				{#each data.positions as p}
					<tr class:selected={selectedTicker === p.etf_ticker} onclick={() => toggleDetail(p.etf_ticker)} style="cursor:pointer">
						<td><strong>{p.etf_ticker}</strong></td>
						<td>{p.etf_name}</td>
						<td>{p.shares}</td>
						<td>{formatZAR(p.cost_basis_per_share)}</td>
						<td>
							{#if p.last_price != null}
								{formatZAR(p.last_price)}
								{#if p.price_stale}
									<span class="stale-badge">⚠ stale</span>
								{/if}
							{:else}
								-
							{/if}
						</td>
						<td>{formatZAR(p.value_zar)}</td>
						<td>{formatZAR(p.cost_zar)}</td>
						<td class:positive={p.pnl_zar > 0} class:negative={p.pnl_zar < 0}>{formatZAR(p.pnl_zar)}</td>
						<td class:positive={p.pnl_pct > 0} class:negative={p.pnl_pct < 0}>{formatPct(p.pnl_pct)}</td>
						<td>{p.weight_pct}%</td>
						<td>{p.ter}%</td>
						<td>
							<button class="btn-danger btn-sm" onclick={(e) => { e.stopPropagation(); removePosition(p); }}>Remove</button>
						</td>
					</tr>
					{#if selectedTicker === p.etf_ticker}
						<tr>
							<td colspan="12" style="padding:0">
								<PortfolioDetail ticker={p.etf_ticker} shares={p.shares} />
							</td>
						</tr>
					{/if}
				{/each}
			</tbody>
		</table>
	{/if}
{/if}
