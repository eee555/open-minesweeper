import { afterEach, describe, expect, it, vi } from 'vitest';

import { scrollTouchAncestors, SingleTouchScroll } from './touchScroll';

describe('single-finger scrolling', () => {
    it('suspends scrolling with multiple contacts and resumes without accumulated movement', () => {
        const scroll = new SingleTouchScroll();
        scroll.down(1, 100, 100, true);
        expect(scroll.move(1, 70, 80)).toEqual({ x: 30, y: 20 });
        scroll.down(2, 200, 200, true);
        expect(scroll.move(1, 20, 30)).toBeNull();
        expect(scroll.move(2, 180, 170)).toBeNull();
        scroll.up(2);
        expect(scroll.move(1, 15, 25)).toEqual({ x: 5, y: 5 });
        scroll.up(1);
        expect(scroll.move(1, 0, 0)).toBeNull();
    });

    it('counts outside contacts without starting a board scroll, and clears cancelled gestures', () => {
        const scroll = new SingleTouchScroll();
        scroll.down(9, 50, 50, false);
        expect(scroll.move(9, 20, 20)).toBeNull();
        scroll.down(1, 50, 50, true);
        expect(scroll.move(1, 20, 20)).toBeNull();
        scroll.up(9);
        expect(scroll.move(1, 10, 10)).toEqual({ x: 10, y: 10 });
        scroll.reset();
        expect(scroll.move(1, 0, 0)).toBeNull();
        scroll.down(1, 10, 10, true);
        expect(scroll.move(1, 20, 20)).toEqual({ x: -10, y: -10 });
    });
});

describe('touch scroll chaining', () => {
    afterEach(() => vi.unstubAllGlobals());

    function fixture() {
        const doc = { scrollingElement: null as unknown, fullscreenElement: null as unknown };
        const element = (parentElement: unknown, maxX: number, maxY: number, overflow = 'auto') => ({
            ownerDocument: doc,
            parentElement,
            scrollLeft: 0,
            scrollTop: 0,
            overflowX: overflow,
            overflowY: overflow,
            scrollBy({ left, top }: { left: number; top: number }) {
                this.scrollLeft = Math.max(0, Math.min(maxX, this.scrollLeft + left));
                this.scrollTop = Math.max(0, Math.min(maxY, this.scrollTop + top));
            },
        });
        const page = element(null, 0, 1000, 'visible');
        doc.scrollingElement = page;
        const viewport = element(page, 100, 0);
        const surface = element(viewport, 0, 0);
        vi.stubGlobal('getComputedStyle', (target: unknown) => target);
        return { doc, page, viewport, surface: surface as unknown as HTMLElement };
    }

    it('scrolls the inner viewport first, then the page beyond the board edges', () => {
        const { surface, viewport, page } = fixture();
        scrollTouchAncestors(surface, 150, 800);
        expect(viewport.scrollLeft).toBe(100);
        expect(page.scrollTop).toBe(800);
        scrollTouchAncestors(surface, -30, -200);
        expect(viewport.scrollLeft).toBe(70);
        expect(page.scrollTop).toBe(600);
    });

    it('keeps fullscreen movement inside the fullscreen element', () => {
        const { doc, surface, viewport, page } = fixture();
        doc.fullscreenElement = viewport;
        scrollTouchAncestors(surface, 150, 800);
        expect(viewport.scrollLeft).toBe(100);
        expect(page.scrollTop).toBe(0);
    });
});
