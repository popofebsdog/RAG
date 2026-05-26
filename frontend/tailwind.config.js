/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        canvas:   '#F7F9FC',
        surface:  '#FFFFFF',
        rail:     '#EEF3F8',
        border:   '#D7E0EA',
        'border-xl': '#E5ECF3',
        ink:      '#172033',
        text:     '#172033',
        sub:      '#526173',
        faint:    '#7B8797',
        accent:   '#1E4E8C',
        'accent-hi': '#2768B6',
        'accent-bg': '#EAF2FC',
        // Node community colors
        n1: 'oklch(0.48 0.11 225)',
        n2: 'oklch(0.50 0.10 148)',
        n3: 'oklch(0.50 0.11 38)',
        n4: 'oklch(0.50 0.10 298)',
        n5: 'oklch(0.50 0.09 180)',
        // Keep legacy for any remaining usage
        panel:    '#FDFCF9',
        muted:    '#A9A39A',
        success:  '#22c55e',
        warning:  '#f59e0b',
      },
      fontFamily: {
        sans:  ['Inter', '"Noto Sans TC"', 'system-ui', 'sans-serif'],
        serif: ['"Noto Serif TC"', 'serif'],
        mono:  ['DM Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
