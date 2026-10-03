// Site-wide interaction effects, started once from the layout. Both are progressive
// enhancements: without them (or with reduced motion) everything works and looks finished.
//
// - Card spotlight: the card under the pointer gets --mx/--my, which app.css turns into a
//   soft light and a glowing border that follow the cursor.
// - Segmented controls: the selected option's pill slides between options instead of
//   jumping. The pill is the .seg::before pseudo-element, positioned from --pill-* vars, so
//   no DOM is added inside Svelte-managed markup.

const SEG = '.seg';

function placePill(seg: HTMLElement, animate: boolean): void {
	const on = seg.querySelector<HTMLElement>(':scope > button[aria-pressed="true"]');
	if (!on) {
		seg.removeAttribute('data-pill');
		return;
	}
	if (!animate) seg.classList.add('pill-instant');
	seg.style.setProperty('--pill-x', `${on.offsetLeft}px`);
	seg.style.setProperty('--pill-y', `${on.offsetTop}px`);
	seg.style.setProperty('--pill-w', `${on.offsetWidth}px`);
	seg.style.setProperty('--pill-h', `${on.offsetHeight}px`);
	seg.setAttribute('data-pill', '');
	if (!animate) requestAnimationFrame(() => seg.classList.remove('pill-instant'));
}

export function startMotion(): () => void {
	const fine = matchMedia('(hover: hover) and (pointer: fine)').matches;
	let frame = 0;
	let last: PointerEvent | null = null;
	const onMove = (e: PointerEvent) => {
		last = e;
		frame ||= requestAnimationFrame(() => {
			frame = 0;
			const card = (last?.target as Element | null)?.closest?.<HTMLElement>('.card');
			if (!card || !last) return;
			const r = card.getBoundingClientRect();
			card.style.setProperty('--mx', `${last.clientX - r.left}px`);
			card.style.setProperty('--my', `${last.clientY - r.top}px`);
		});
	};
	if (fine) addEventListener('pointermove', onMove, { passive: true });

	// Pills: place every segmented control now, again when a selection changes, when new
	// controls appear (navigation, data loading), and on resize (wrapping changes offsets).
	const seen = new WeakSet<HTMLElement>();
	let scanQueued = false;
	const scan = () => {
		for (const seg of document.querySelectorAll<HTMLElement>(SEG)) {
			placePill(seg, seen.has(seg));
			seen.add(seg);
		}
	};
	const mo = new MutationObserver((records) => {
		let structural = false;
		for (const r of records) {
			if (r.type === 'attributes') {
				const seg = (r.target as Element).closest<HTMLElement>(SEG);
				if (seg) placePill(seg, true);
			} else structural = true;
		}
		// Batch DOM churn (tables rendering, charts) into one scan per frame.
		if (structural && !scanQueued) {
			scanQueued = true;
			requestAnimationFrame(() => {
				scanQueued = false;
				scan();
			});
		}
	});
	mo.observe(document.body, {
		subtree: true,
		childList: true,
		attributes: true,
		attributeFilter: ['aria-pressed']
	});
	const onResize = () => {
		for (const seg of document.querySelectorAll<HTMLElement>(SEG)) placePill(seg, false);
	};
	addEventListener('resize', onResize, { passive: true });
	document.fonts?.ready.then(onResize).catch(() => {});
	scan();

	return () => {
		removeEventListener('pointermove', onMove);
		removeEventListener('resize', onResize);
		cancelAnimationFrame(frame);
		mo.disconnect();
	};
}
