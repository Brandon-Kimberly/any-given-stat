// See https://svelte.dev/docs/kit/types#app.d.ts
declare global {
	namespace App {}
	/** True in the public (GitHub Pages) build; see src/lib/hosted.ts. */
	const __HOSTED__: boolean;
	/** The public site's address (PUBLIC_SITE_URL at build), '' locally. */
	const __SITE_URL__: string;
}

export {};
