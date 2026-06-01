/** Format a number as ZAR currency: "R 1,234.56" */
export function formatZAR(n) {
	if (n === null || n === undefined || n === '-') return '-';
	return 'R ' + Number(n).toLocaleString('en-ZA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Format a number as percentage: "12.34%" */
export function formatPct(n) {
	if (n === null || n === undefined) return '-';
	return Number(n).toFixed(2) + '%';
}

/** Theme management */
export function getInitialTheme() {
	if (typeof window === 'undefined') return 'dark';
	const stored = localStorage.getItem('theme');
	if (stored === 'light' || stored === 'dark') return stored;
	return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function applyTheme(t) {
	if (typeof document === 'undefined') return;
	document.documentElement.setAttribute('data-theme', t);
	localStorage.setItem('theme', t);
}
