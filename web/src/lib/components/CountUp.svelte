<script lang="ts">
	// Counts the numbers inside a formatted value up to their final values ("+0.12", "3-1",
	// "#4 of 32"), keeping the formatter's decimals, signs and separators. Changes animate from
	// the previous value when the shape matches. Instant under prefers-reduced-motion.
	let { text, duration = 650 }: { text: string; duration?: number } = $props();

	const NUM = /(\d[\d,]*(?:\.\d+)?)/;
	const reduce =
		typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

	// svelte-ignore state_referenced_locally
	let shown = $state(reduce ? text : text.replace(/\d/g, '0'));
	let prev: number[] | null = null;

	function render(token: string, v: number): string {
		const dec = token.split('.')[1]?.length ?? 0;
		return token.includes(',')
			? v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
			: v.toFixed(dec);
	}

	$effect(() => {
		const target = text;
		const parts = target.split(NUM);
		const nums = parts.filter((_, i) => i % 2).map((p) => parseFloat(p.replace(/,/g, '')));
		const from = prev && prev.length === nums.length ? prev : nums.map(() => 0);
		prev = nums;
		if (reduce || !nums.length) {
			shown = target;
			return;
		}
		const start = performance.now();
		let raf = 0;
		const step = (t: number) => {
			const k = Math.min(1, (t - start) / duration);
			const e = 1 - (1 - k) ** 3;
			let j = 0;
			shown =
				k === 1
					? target
					: parts
							.map((p, i) => {
								if (!(i % 2)) return p;
								const v = from[j] + (nums[j] - from[j]) * e;
								j++;
								return render(p, v);
							})
							.join('');
			if (k < 1) raf = requestAnimationFrame(step);
		};
		raf = requestAnimationFrame(step);
		return () => cancelAnimationFrame(raf);
	});
</script>

<span class="tnum">{shown}</span>
