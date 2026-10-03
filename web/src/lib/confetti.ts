// A short burst of confetti from a point, in the given colors (e.g. a team's). Plain DOM +
// Web Animations: no canvas, no dependency, cleans itself up. Skipped under reduced motion.

export function confetti(x: number, y: number, colors: string[], count = 46): void {
	if (typeof document === 'undefined') return;
	if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
	const layer = document.createElement('div');
	layer.setAttribute('aria-hidden', 'true');
	layer.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:300;overflow:hidden';
	document.body.appendChild(layer);
	const palette = colors.length ? colors : ['#3b82f6', '#22d3ee', '#a78bfa'];
	let done = 0;
	for (let i = 0; i < count; i++) {
		const p = document.createElement('span');
		const w = 5 + Math.random() * 6;
		const h = w * (0.4 + Math.random() * 0.8);
		p.style.cssText = `position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-radius:${Math.random() < 0.3 ? '50%' : '2px'};background:${palette[i % palette.length]};box-shadow:0 0 0 1px rgba(255,255,255,.25)`;
		layer.appendChild(p);
		const angle = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.1;
		const speed = 180 + Math.random() * 260;
		const dx = Math.cos(angle) * speed;
		const dy = Math.sin(angle) * speed;
		const spin = (Math.random() - 0.5) * 1080;
		const a = p.animate(
			[
				{ transform: 'translate(-50%, -50%) rotate(0deg)', opacity: 1 },
				{
					transform: `translate(${dx * 0.75}px, ${dy * 0.75}px) rotate(${spin * 0.6}deg)`,
					opacity: 1,
					offset: 0.45
				},
				{ transform: `translate(${dx}px, ${dy + 260}px) rotate(${spin}deg)`, opacity: 0 }
			],
			{ duration: 1100 + Math.random() * 700, easing: 'cubic-bezier(0.2, 0.6, 0.4, 1)' }
		);
		a.onfinish = () => {
			if (++done === count) layer.remove();
		};
	}
}
