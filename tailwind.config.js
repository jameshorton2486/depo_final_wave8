module.exports = {
    content: [
        "./frontend/index.html",
        "./frontend/screens/**/*.html",
        "./frontend/assets/js/**/*.js",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ["Inter", "sans-serif"],
                mono: ["JetBrains Mono", "monospace"],
                serif: ["Lora", "serif"],
            },
            colors: {
                legal: {
                    50: "#f8fafc",
                    100: "#f1f5f9",
                    800: "#1e293b",
                    900: "#0f172a",
                    gold: "#d97706",
                    emerald: "#059669",
                    blue: "#2563eb",
                    red: "#dc2626",
                },
            },
        },
    },
};
