/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#0F172A',
        'etm-green': '#16A34A',
        'etm-green-dark': '#3B6D11',
        'etm-green-bg': '#EAF3DE',
        warning: '#854F0B',
        'warning-bg': '#FAEEDA',
        info: '#185FA5',
        'info-bg': '#E6F1FB',
        danger: '#A32D2D',
        'danger-bg': '#FCEBEB',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        card: '8px',
        btn: '6px',
      },
    },
  },
  plugins: [],
}

