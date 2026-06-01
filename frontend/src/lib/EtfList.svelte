<script>
	import { onMount } from 'svelte';
	import { formatPct } from '$lib/utils.js';
	import { api } from '$lib/api.js';
	import EtfDetail from './EtfDetail.svelte';

	let etfs = $state([]);
	let error = $state(null);
	let loading = $state(true);
	let selected = $state(null);

	// Inline add form state
	let addTicker = $state(null);
	let addShares = $state('');
	let addCost = $state('');
	let adding = $state(false);
	let addError = $state(null);
	let addedTickers = $state(new Set());

	onMount(async () => {
		try {
			const d = await api.listEtfs();
			etfs = d.etfs;
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	});

	async function showDetail(e) {
		if (selected?.ticker === e.ticker) {
			selected = null;
		} else {
			selected = await api.etfDetail(e.ticker);
		}
	}

	function startAdd(ev, ticker) {
		ev.stopPropagation();
		addTicker = ticker;
		addShares = '';
		addCost = '';
		addError = null;
	}

	function cancelAdd(ev) {
		ev.stopPropagation();
		addTicker = null;
	}

	async function confirmAdd(ev, ticker) {
		ev.stopPropagation();
		const shares = parseFloat(addShares);
		if (!shares || shares <= 0) {
			addError = 'Enter valid shares';
			return;
		}
		adding = true;
		addError = null;
		try {
			await api.addPosition({ etf_ticker: ticker, shares, cost_basis_per_share: parseFloat(addCost) || 0 });
			addedTickers = new Set([...addedTickers, ticker]);
			addTicker = null;
			setTimeout(() => {
				addedTickers = new Set([...addedTickers].filter(t => t !== ticker));
			}, 2000);
		} catch (e) {
			addError = e.message;
		} finally {
			adding = false;
		}
	}
</script>

{#if error}
	<div class="error">Error: {error}</div>
{:else if loading}
	<div class="empty">Loading ETFs...</div>
{:else}
	<h2>ETFs</h2>
	{#if etfs.length === 0}
		<div class="empty">No ETFs configured.</div>
	{:else}
		<table class="data-table">
			<thead>
				<tr>
					<th>Ticker</th>
					<th>Name</th>
					<th>Benchmark</th>
					<th>TER</th>
					<th>Holdings</th>
					<th style="width:160px">Action</th>
				</tr>
			</thead>
			<tbody>
				{#each etfs as e}
					<tr
						class:selected={selected?.ticker === e.ticker}
						onclick={() => showDetail(e)}
						style="cursor:pointer"
					>
						<td><strong>{e.ticker}</strong></td>
						<td>{e.name}</td>
						<td class="subtitle">{e.benchmark}</td>
						<td>{e.ter != null ? e.ter + '%' : '-'}</td>
						<td>{e.holding_count}</td>
						<td>
							{#if addTicker === e.ticker}
								<div
									class="add-row"
									style="margin:0;padding:8px;display:flex;flex-direction:column;gap:4px"
									onclick={(ev) => ev.stopPropagation()}
								>
									<input type="number" step="any" bind:value={addShares} placeholder="Shares" />
									<input type="number" step="any" bind:value={addCost} placeholder="Cost/share" />
									{#if addError}
										<span style="color:var(--red);font-size:10px">{addError}</span>
									{/if}
									<div style="display:flex;gap:4px">
										<button class="btn-primary btn-sm" disabled={adding} onclick={(ev) => confirmAdd(ev, e.ticker)}>
											{adding ? '...' : 'Add'}
										</button>
										<button class="btn-danger btn-sm" onclick={(ev) => cancelAdd(ev)}>Cancel</button>
									</div>
								</div>
							{:else}
								<button class="btn-primary btn-sm" onclick={(ev) => startAdd(ev, e.ticker)}>
									{addedTickers.has(e.ticker) ? '✓ Added' : '+ Portfolio'}
								</button>
							{/if}
						</td>
					</tr>
					{#if selected?.ticker === e.ticker}
						<tr>
							<td colspan="6" style="padding:0">
								<EtfDetail etf={selected} />
							</td>
						</tr>
					{/if}
				{/each}
			</tbody>
		</table>
	{/if}
{/if}
