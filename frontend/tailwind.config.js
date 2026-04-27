/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        // Anthropic / Claude theming via CSS variables
        base: 'rgb(var(--color-base) / <alpha-value>)',
        surface: 'rgb(var(--color-surface) / <alpha-value>)',
        subtle: 'rgb(var(--color-subtle) / <alpha-value>)',
        line: 'rgb(var(--color-line) / <alpha-value>)',
        ink: {
          DEFAULT: 'rgb(var(--color-ink) / <alpha-value>)',
          muted: 'rgb(var(--color-ink-muted) / <alpha-value>)',
          subtle: 'rgb(var(--color-ink-subtle) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'rgb(var(--color-accent) / <alpha-value>)',
          hover: 'rgb(var(--color-accent-hover) / <alpha-value>)',
          soft: 'rgb(var(--color-accent-soft) / <alpha-value>)',
        },
        sev: {
          p0: 'rgb(var(--color-sev-p0) / <alpha-value>)',
          p0bg: 'rgb(var(--color-sev-p0-bg) / <alpha-value>)',
          p1: 'rgb(var(--color-sev-p1) / <alpha-value>)',
          p1bg: 'rgb(var(--color-sev-p1-bg) / <alpha-value>)',
          p2: 'rgb(var(--color-sev-p2) / <alpha-value>)',
          p2bg: 'rgb(var(--color-sev-p2-bg) / <alpha-value>)',
          p3: 'rgb(var(--color-sev-p3) / <alpha-value>)',
          p3bg: 'rgb(var(--color-sev-p3-bg) / <alpha-value>)',
        },
      },
    },
  },
  plugins: [],
}
