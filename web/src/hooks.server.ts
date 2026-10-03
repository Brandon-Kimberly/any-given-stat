// Runs while SvelteKit prerenders each route (and in `vite dev`): fills app.html's link-preview
// tokens with that route's title and description (src/lib/seo.ts). Image and page URLs must be
// absolute for chat apps to use them, so they're built on the public site's address
// (PUBLIC_SITE_URL, set by the deploy workflow; locally they fall back to the request origin).
import type { Handle } from '@sveltejs/kit';
import { base } from '$app/paths';
import { escapeAttr, OG_IMAGE_VERSION, pageMeta } from '$lib/seo';

export const handle: Handle = ({ event, resolve }) => {
	const path = event.url.pathname.slice(base.length) || '/';
	const meta = pageMeta(path);
	const site = (__SITE_URL__ || event.url.origin + base).replace(/\/$/, '');
	const tokens: Record<string, string> = {
		__OG_TITLE__: meta.title,
		__OG_DESCRIPTION__: meta.description,
		__OG_URL__: site + (path === '/' ? '/' : path),
		__OG_IMAGE__: `${site}/og.png?v=${OG_IMAGE_VERSION}`
	};
	return resolve(event, {
		transformPageChunk: ({ html }) =>
			html.replace(/__OG_[A-Z]+__/g, (t) => (t in tokens ? escapeAttr(tokens[t]) : t))
	});
};
