/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        discord: {
          bg:           '#313338',
          sidebar:      '#2B2D31',
          dark:         '#1E1F22',
          darker:       '#111214',
          input:        '#1E1F22',
          hover:        '#35373C',
          active:       '#404249',
          faint:        '#4E5058',
          muted:        '#80848E',
          text:         '#DBDEE1',
          white:        '#FFFFFF',
          blurple:      '#5865F2',
          blurple_hover:'#4752C4',
          green:        '#23A55A',
          red:          '#F23F43',
          yellow:       '#F0B232',
          link:         '#00A8FC',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans', 'Helvetica Neue', 'Helvetica', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
