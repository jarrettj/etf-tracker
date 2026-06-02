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

/** Table helpers ───────────────────────────────────────────────────────────── */

/** Return a new array sorted by `key`. Direction is 'asc' or 'desc'.
 *  Numeric vs string comparison is auto-detected from the first non-null value. */
export function sortRows(rows, key, dir = 'asc') {
	if (!key) return rows;
	const sign = dir === 'desc' ? -1 : 1;
	return [...rows].sort((a, b) => {
		const av = a?.[key];
		const bv = b?.[key];
		if (av == null && bv == null) return 0;
		if (av == null) return 1;   // nulls sort last regardless of direction
		if (bv == null) return -1;
		if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * sign;
		return String(av).localeCompare(String(bv)) * sign;
	});
}

/** Case-insensitive substring filter across the given `fields`. */
export function filterRows(rows, query, fields) {
	const q = (query || '').trim().toLowerCase();
	if (!q) return rows;
	return rows.filter((r) =>
		fields.some((f) => String(r?.[f] ?? '').toLowerCase().includes(q))
	);
}

/** Build a CSV string. `columns` is [{ key, label }]. Values are escaped/quoted. */
export function toCsv(rows, columns) {
	const esc = (v) => {
		const s = v == null ? '' : String(v);
		return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
	};
	const header = columns.map((c) => esc(c.label)).join(',');
	const lines = rows.map((r) => columns.map((c) => esc(r?.[c.key])).join(','));
	return [header, ...lines].join('\n');
}

/** Trigger a client-side download of `csv` as `filename` (no dependencies). */
export function downloadCsv(filename, csv) {
	if (typeof document === 'undefined') return;
	const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
	URL.revokeObjectURL(url);
}
