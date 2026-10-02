import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		adapter: adapter({ fallback: '404.html' }),
		// GitHub Pages serves the site under /<repo>; set BASE_PATH there.
		paths: { base: process.env.BASE_PATH ?? '' }
	}
};

export default config;
