/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans:  ['"DM Sans"', 'system-ui', 'sans-serif'],
        serif: ['"Playfair Display"', 'Georgia', 'serif'],
        mono:  ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        // Warm cream/parchment backgrounds
        paper: {
          50:  '#fdfaf5',
          100: '#f5ede0',
          200: '#ecdcc8',
          300: '#dcc8a8',
          400: '#c8a878',
          500: '#9a7a58',
          600: '#7a5838',
          700: '#5a3e28',
          800: '#3a2010',
          900: '#1a0e06',
        },
        // Warm orange-amber accent (main CTA, active states)
        accent: {
          50:  '#fff7ee',
          100: '#fde8cc',
          200: '#fac890',
          300: '#f0a040',
          400: '#e8742a',   // primary — warm orange
          500: '#c85018',
          600: '#a03810',
          700: '#6a2208',
        },
        // Amber/gold for secondary highlights
        gold: {
          100: '#fdf4d0',
          300: '#f0c840',
          400: '#d49428',
          500: '#a87010',
          600: '#7a5008',
        },
        // Muted sage
        sage: {
          100: '#edf5e8',
          400: '#5a8a48',
          500: '#3e6830',
          700: '#224018',
        },
        // Warm rust / Phoebe wellness
        rust: {
          100: '#fae8e0',
          200: '#f5cfc0',
          400: '#d06040',
          500: '#a84020',
          700: '#6a2010',
        },
        // Friends / Central Perk palette
        friends: {
          purple:      '#6B3FA0',
          'purple-dark': '#4A2870',
          'purple-light': '#9B6BC4',
          frame:       '#F4D03F',
          'frame-dark': '#D4AF37',
          sofa:        '#E8751A',
          'sofa-dark': '#C85018',
          cream:       '#FAF0E4',
          awning:      '#3D6B4F',
        },
        perk: {
          100: '#f5ebe0',
          200: '#e8d5c4',
          400: '#8B6914',
          500: '#6B4423',
          600: '#4A3728',
          700: '#3a2a1e',
        },
        // Rose/blush — Rachel (fashion & style)
        rose: {
          50:  '#fff5f7',
          100: '#fde8ed',
          200: '#f9c8d4',
          400: '#e87090',
          500: '#c84868',
          600: '#a03050',
        },
      },
      boxShadow: {
        'card':    '0 2px 12px 0 rgba(90,50,20,0.08), 0 1px 3px 0 rgba(90,50,20,0.06)',
        'card-lg': '0 6px 32px 0 rgba(90,50,20,0.12), 0 2px 8px 0 rgba(90,50,20,0.08)',
        'input':   '0 1px 4px 0 rgba(90,50,20,0.10)',
      },
    },
  },
  plugins: [],
}
