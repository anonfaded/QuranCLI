module.exports = {
    content: ["./core/web/**/*.{html,js}"],
    theme: {
      extend: {
        colors: {
          gray: {
            950: '#000000', // Pure black for AMOLED
            900: '#0A0A0A', // Slightly lighter black
            800: '#121212', // Card background
            700: '#1A1A1A', // Hover states
          },
          red: {
            600: '#FF1744', // Brighter red for better contrast
            500: '#FF4081', // Secondary red
            400: '#FF80AB', // Accent red
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