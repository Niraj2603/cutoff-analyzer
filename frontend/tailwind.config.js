/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#102034",
        mist: "#eef6fb",
        gold: "#f1c76b",
        coral: "#ee7d52",
        pine: "#204b47",
        slate: "#5f7185",
      },
      fontFamily: {
        display: ['"Trebuchet MS"', '"Segoe UI"', "sans-serif"],
        body: ['"Verdana"', '"Trebuchet MS"', "sans-serif"],
      },
      boxShadow: {
        panel: "0 24px 60px rgba(16, 32, 52, 0.14)",
      },
      animation: {
        rise: "rise 0.6s ease-out",
        pulsebar: "pulsebar 1.6s ease-in-out infinite",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(18px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulsebar: {
          "0%, 100%": { transform: "scaleX(0.98)" },
          "50%": { transform: "scaleX(1)" },
        },
      },
    },
  },
  plugins: [],
};
