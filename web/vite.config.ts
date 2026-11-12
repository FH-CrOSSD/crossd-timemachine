import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  // DuckDB-WASM ships its own worker and wasm files; Vite copies them into the build (offline booth).
  optimizeDeps: { exclude: ['@duckdb/duckdb-wasm'] },
  test: { include: ['src/**/*.test.ts'] }
});
