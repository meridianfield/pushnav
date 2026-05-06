import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    proxy: {
      "/ws":         { target: "ws://localhost:8080", ws: true },
      "/frame.mjpg": "http://localhost:8080",
      "/api":        "http://localhost:8080",
      "/sounds":     "http://localhost:8080",
      "/assets":     "http://localhost:8080",
    },
  },
});
