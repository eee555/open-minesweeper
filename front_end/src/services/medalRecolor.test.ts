import { describe, expect, it } from 'vitest';

import { recolorMedalPixels } from './medalRecolor';

describe('medal metal recolor', () => {
    it('turns gold pixels copper or silver and leaves highlights and cool pixels', () => {
        const data = new Uint8ClampedArray([
            200, 150, 40, 255,
            250, 240, 220, 255,
            50, 40, 40, 255,
            80, 80, 90, 255,
        ]);
        recolorMedalPixels(data, 'b');
        expect(Array.from(data)).toEqual([
            205, 99, 32, 255,
            250, 240, 220, 255,
            50, 40, 40, 255,
            80, 80, 90, 255,
        ]);
        const silver = new Uint8ClampedArray([200, 150, 40, 255]);
        recolorMedalPixels(silver, 'i');
        expect(Array.from(silver)).toEqual([162, 159, 149, 255]);
    });
});
