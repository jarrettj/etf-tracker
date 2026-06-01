<script>
	import { onMount } from 'svelte';
	import { getInitialTheme, applyTheme } from '$lib/utils.js';
	import Portfolio from '$lib/Portfolio.svelte';
	import EtfList from '$lib/EtfList.svelte';
	import ConsolidatedHoldings from '$lib/ConsolidatedHoldings.svelte';
	import StatusMeta from '$lib/StatusMeta.svelte';

	const tabs = [
		{ id: 'portfolio', label: 'Portfolio' },
		{ id: 'etfs', label: 'ETFs' },
		{ id: 'holdings', label: 'Consolidated' },
		{ id: 'status', label: 'Status' },
	];

	let activeTab = $state('portfolio');
	let theme = $state('dark');

	onMount(() => {
		theme = getInitialTheme();
		applyTheme(theme);
	});

	function toggleTheme() {
		theme = theme === 'dark' ? 'light' : 'dark';
		applyTheme(theme);
	}

	function setTab(id) {
		activeTab = id;
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
		{#if activeTab === 'portfolio'}
			<Portfolio />
		{:else if activeTab === 'etfs'}
			<EtfList />
		{:else if activeTab === 'holdings'}
			<ConsolidatedHoldings />
		{:else if activeTab === 'status'}
			<StatusMeta />
		{/if}
	</main>
</div>
