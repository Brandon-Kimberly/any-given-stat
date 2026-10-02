import { describe, expect, it } from 'vitest';
import { pushRecent } from './recent';

describe('pushRecent', () => {
	it('moves a revisit to the front and caps the list', () => {
		const list = ['/a/', '/b/', '/c/', '/d/', '/e/', '/f/'];
		expect(pushRecent('/c/', list)).toEqual(['/c/', '/a/', '/b/', '/d/', '/e/', '/f/']);
		expect(pushRecent('/g/', list)).toEqual(['/g/', '/a/', '/b/', '/c/', '/d/', '/e/']);
	});
});
