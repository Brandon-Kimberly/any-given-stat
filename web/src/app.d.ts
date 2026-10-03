// See https://svelte.dev/docs/kit/types#app.d.ts
declare global {
	namespace App {}
	/** True in the public (GitHub Pages) build; see src/lib/hosted.ts. */
	const __HOSTED__: boolean;
}

export {};
