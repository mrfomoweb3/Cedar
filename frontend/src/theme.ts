export type Theme = 'light' | 'dark';
const KEY = 'cedar-theme';

export function getInitialTheme(): Theme {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === 'light' || saved === 'dark') return saved;
    if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) return 'dark';
  } catch { /* SSR / blocked storage */ }
  return 'light';
}

export function applyTheme(t: Theme): void {
  document.documentElement.setAttribute('data-theme', t);
  try { localStorage.setItem(KEY, t); } catch { /* ignore */ }
}

/** Resolved chart colors from the active theme's CSS variables. SVG stroke
 *  attributes don't resolve var(), so recharts needs concrete values. */
export function chartColors() {
  const s = getComputedStyle(document.documentElement);
  const g = (n: string) => s.getPropertyValue(n).trim();
  return {
    grid: g('--border'),
    axis: g('--text-3'),
    panel: g('--elevated'),
    border: g('--border'),
    text: g('--text'),
  };
}
