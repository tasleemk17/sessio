import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5190, // not 5173/5180: those belong to the Tomato and Job Radar apps on this machine
    strictPort: true,
    proxy: { "/api": "http://localhost:8010" },
  },
});
