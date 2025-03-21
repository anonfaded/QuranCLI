module.exports = {
    content: ["./core/web/**/*.{html,js}"],
    theme: {
      extend: {
        colors: {
          gray: {
            950: '#0a0a0a',
            900: '#121212',
            800: '#1e1e1e',
            700: '#252525',
          },
          red: {
            600: '#e63946',
            500: '#f94144',
            400: '#ffccd5',
          }
        },
        animation: {
          'gradient-x': 'gradient 3s linear infinite',
          'scale-in': 'scale-in 1.5s ease forwards',
          'fade-in': 'fade-in 0.5s ease forwards',
        },
        keyframes: {
          gradient: {
            '0%': { backgroundPosition: '0% 50%' },
            '50%': { backgroundPosition: '100% 50%' },
            '100%': { backgroundPosition: '0% 50%' },
          },
          'scale-in': {
            'to': { transform: 'scaleX(1)' },
          },
          'fade-in': {
            'to': { transform: 'translateY(0)', opacity: '1' },
          },
        },
        boxShadow: {
          'inner-top': 'inset 0 4px 8px 0 rgba(0, 0, 0, 0.1)',
        },
      },
    },
    plugins: [],
  }