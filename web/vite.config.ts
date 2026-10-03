import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit()],
	// The public build (PUBLIC_HOSTED=1, set by the deploy workflow) has no local server: no
	// /api probes, no Sync, no ESPN proxy. See src/lib/hosted.ts.
	define: {
		__HOSTED__: JSON.stringify(process.env.PUBLIC_HOSTED === '1'),
		// The public site's address, for absolute link-preview URLs (src/hooks.server.ts).
		__SITE_URL__: JSON.stringify(process.env.PUBLIC_SITE_URL ?? '')
	},
	optimizeDeps: { exclude: ['@duckdb/duckdb-wasm'] },
	test: { include: ['src/**/*.test.ts'] }
});
