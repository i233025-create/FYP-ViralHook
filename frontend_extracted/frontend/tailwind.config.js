/** @type {import('tailwindcss').Config} */

// All colours are theme tokens (CSS variables in src/index.css). Dark panels
// (class "on-dark") redefine the text/line/surface tokens, so every UI-kit
// component inside them switches to cream-on-black by itself.
const token = (name) => `rgb(var(--vh-${name}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        vh: {
          bg: token('bg'),             // page (cream)
          surface: token('surface'),   // cards (white; black inside dark panels)
          raised: token('raised'),     // tiles, hover, selected rows
          input: token('input'),       // fields, wells
          line: token('line'),         // borders and dividers (use with /opacity)
          text: token('text'),         // body text
          strong: token('strong'),     // emphasised text
          muted: token('muted'),       // labels (black on cream, cream on black)
          faint: token('faint'),       // hints
          head: token('head'),         // headings
          title: token('title'),       // big page titles
          accent: token('accent'),     // mustard: primary actions, current step, highlight box
          'accent-hover': token('accent-hover'),
          'accent-end': token('accent-end'),
          accent2: token('accent2'),   // red: step badges, numbering, plus marks
          edge: token('edge'),         // card outlines
          ink: token('ink'),           // text on mustard
          steel: token('steel'),       // dark panels
          night: token('night'),       // fixed black (#1E1E1E)
          cream: token('cream'),       // fixed cream (#F1ECE4)
          frame: token('frame'),       // locked film frames, tiles on black
          pale: token('pale'),         // pale mustard (background art)
          art: token('art'),           // background line art
          ok: token('ok'),
          warn: token('warn'),
          bad: token('bad'),
          info: token('info'),
          // Scene segments (consistent everywhere a segment appears)
          hook: token('seg-hook'),
          setup: token('seg-setup'),
          main: token('seg-main'),
          evidence: token('seg-evidence'),
          cta: token('seg-cta'),
        },
      },
      fontFamily: {
        sans: ['"Inter Variable"', 'Inter', 'system-ui', 'sans-serif'],
        display: ['"Bebas Neue"', 'Impact', 'sans-serif'],
        mono: ['"JetBrains Mono Variable"', '"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      opacity: { 7: '0.07', 12: '0.12' },
      screens: { short: { raw: '(max-height: 760px)' } },
      maxWidth: {
        page: '72rem',
      },
      boxShadow: {
        // solid offset shadows, as in the design (no blur)
        hard: '6px 6px 0 0 rgb(var(--vh-night))',
        'hard-sm': '4px 4px 0 0 rgb(var(--vh-night))',
        'hard-lg': '9px 9px 0 0 rgb(var(--vh-night))',
        accent: '7px 7px 0 0 rgb(var(--vh-accent))',
        'accent-sm': '5px 5px 0 0 rgb(var(--vh-accent))',
        panel: '0 18px 40px -20px rgb(30 30 30 / 0.45)',
        glow: '6px 6px 0 0 rgb(var(--vh-accent))',
      },
      keyframes: {
        fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
        rise: { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'none' } },
        drawerIn: { from: { transform: 'translateX(-100%)' }, to: { transform: 'none' } },
        float: { '0%, 100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-8px)' } },
        shimmer: { '0%': { transform: 'translateX(-120%)' }, '100%': { transform: 'translateX(320%)' } },
        strip: { from: { backgroundPosition: '0 0' }, to: { backgroundPosition: '56px 0' } },
      },
      animation: {
        fadeIn: 'fadeIn .2s ease-out both',
        rise: 'rise .28s cubic-bezier(.2,.7,.2,1) both',
        drawerIn: 'drawerIn .22s cubic-bezier(.2,.7,.2,1) both',
        float: 'float 7s ease-in-out infinite',
        shimmer: 'shimmer 1.8s ease-in-out infinite',
        strip: 'strip 1.2s linear infinite',
      },
    },
  },
  plugins: [],
}
