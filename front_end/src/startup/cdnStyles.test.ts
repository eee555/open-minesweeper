import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { loadCdnStyles } from './cdnStyles';

interface Link {
    rel: string;
    href: string;
    dataset: Record<string, string>;
    onload: (() => void) | null;
    onerror: (() => void) | null;
    remove: () => void;
}

const styles = [
    { id: 'element-plus', cdn: 'https://cdn.test/element.css', local: '/assets/vendor/element.css' },
    { id: 'primeicons', cdn: 'https://cdn.test/icons.css', local: '/assets/vendor/icons.css', font: '16px primeicons' },
];
const anchor = {};
const overrides = {};
let nodes: object[];
let links: Link[];
const fontLoad = vi.fn(() => Promise.resolve([{}]));
const chinese = { textContent: '' };
const english = { textContent: '' };
const spanish = { textContent: '' };
const label = {
    hidden: true,
    querySelector(selector: string) {
        return selector.includes('zh-CN') ? chinese : selector.includes('es') ? spanish : english;
    },
};
const progress = { max: 0, value: 0, setAttribute: vi.fn() };

beforeEach(() => {
    vi.useFakeTimers();
    nodes = [anchor, overrides];
    links = [];
    fontLoad.mockReset().mockResolvedValue([{}]);
    chinese.textContent = '';
    english.textContent = '';
    label.hidden = true;
    progress.max = 0;
    progress.value = 0;
    vi.stubGlobal('document', {
        currentScript: anchor,
        querySelector(selector: string) {
            return selector.includes('progress') ? progress : label;
        },
        fonts: { load: fontLoad },
        head: {
            querySelector() {
                return null;
            },
            insertBefore(node: object, before: object) {
                nodes.splice(nodes.indexOf(before), 0, node);
            },
        },
        createElement() {
            const link: Link = {
                rel: '',
                href: '',
                dataset: {},
                onload: null,
                onerror: null,
                remove() {
                    nodes.splice(nodes.indexOf(link), 1);
                },
            };
            links.push(link);
            return link;
        },
    });
});

afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
});

describe('CDN stylesheet fallback', () => {
    it('loads both CDN styles and verifies the font without downloading local copies', async () => {
        const ready = loadCdnStyles(styles);
        expect(progress.max).toBe(3);
        expect(progress.value).toBe(0);
        expect(english.textContent).toContain('Loading from CDN');
        links[0].onload?.();
        links[1].onload?.();
        await ready;
        expect(progress.value).toBe(3);
        expect(chinese.textContent).toContain('界面资源 3/3');
        await vi.runAllTimersAsync();
        expect(links.map((link) => link.href)).toEqual(styles.map((style) => style.cdn));
        expect(fontLoad).toHaveBeenCalledWith('16px primeicons', '\ue900');
    });

    it('retries a failed stylesheet locally in the same position before overrides', async () => {
        const ready = loadCdnStyles([styles[0]]);
        const [cdn] = links;
        cdn.onerror?.();
        expect(links[1].href).toBe(styles[0].local);
        expect(english.textContent).toContain('CDN unavailable');
        expect(nodes).toEqual([links[1], anchor, overrides]);
        links[1].onload?.();
        await ready;
    });

    it('falls back on timeout even when the CDN produces no error event', async () => {
        const ready = loadCdnStyles([styles[0]]);
        await vi.advanceTimersByTimeAsync(3999);
        expect(links).toHaveLength(1);
        await vi.advanceTimersByTimeAsync(1);
        expect(links[1].href).toBe(styles[0].local);
        expect(english.textContent).toContain('CDN is slow');
        links[1].onload?.();
        await ready;
    });

    it('falls back when CSS succeeds but the icon font fails', async () => {
        fontLoad.mockRejectedValueOnce(new Error('CDN font unavailable'));
        const ready = loadCdnStyles([styles[1]]);
        links[0].onload?.();
        await vi.advanceTimersByTimeAsync(0);
        expect(progress.value).toBe(1);
        expect(links[1].href).toBe(styles[1].local);
        expect(nodes).not.toContain(links[0]);
        links[1].onload?.();
        await ready;
        expect(progress.value).toBe(2);
        expect(fontLoad).toHaveBeenCalledTimes(2);
    });

    it('times out a hanging font download as part of the same CDN deadline', async () => {
        fontLoad.mockImplementationOnce(() => new Promise(() => undefined));
        const ready = loadCdnStyles([styles[1]]);
        links[0].onload?.();
        await vi.advanceTimersByTimeAsync(4000);
        expect(links[1].href).toBe(styles[1].local);
        links[1].onload?.();
        await ready;
    });

    it('ignores late CDN events after switching to the local stylesheet', async () => {
        const ready = loadCdnStyles([styles[0]]);
        const lateLoad = links[0].onload;
        const lateError = links[0].onerror;
        await vi.advanceTimersByTimeAsync(4000);
        lateLoad?.();
        lateError?.();
        let done = false;
        void ready.then(() => {
            done = true;
        });
        await vi.advanceTimersByTimeAsync(0);
        expect(done).toBe(false);
        expect(links).toHaveLength(2);
        links[1].onload?.();
        await ready;
    });

    it('rejects if the local stylesheet also fails', async () => {
        const ready = loadCdnStyles([styles[0]]);
        const rejected = expect(ready).rejects.toThrow('Failed to load stylesheet: element-plus');
        links[0].onerror?.();
        links[1].onerror?.();
        await rejected;
    });

    it('rejects if the local font or CSS never finishes', async () => {
        const ready = loadCdnStyles([styles[1]]);
        const rejected = expect(ready).rejects.toThrow('Failed to load stylesheet: primeicons');
        links[0].onerror?.();
        await vi.advanceTimersByTimeAsync(15000);
        await rejected;
    });

    it('treats a missing font declaration as a failure instead of accepting a fallback font', async () => {
        fontLoad.mockResolvedValueOnce([]);
        const ready = loadCdnStyles([styles[1]]);
        links[0].onload?.();
        await vi.advanceTimersByTimeAsync(0);
        expect(links[1].href).toBe(styles[1].local);
        links[1].onload?.();
        await ready;
    });

    it('updates the placeholder after resources finish before the body is parsed', async () => {
        const doc = document;
        let parsed: (() => void) | undefined;
        vi.stubGlobal('document', {
            currentScript: doc.currentScript,
            fonts: doc.fonts,
            head: doc.head,
            createElement: () => doc.createElement('link'),
            readyState: 'loading',
            querySelector: () => null,
            addEventListener(_event: string, callback: () => void) {
                parsed = callback;
            },
        });
        const ready = loadCdnStyles(styles);
        links[0].onload?.();
        links[1].onload?.();
        await ready;
        expect(label.hidden).toBe(true);
        vi.stubGlobal('document', doc);
        parsed?.();
        expect(label.hidden).toBe(false);
        expect(chinese.textContent).toContain('界面资源 3/3');
        expect(progress.value).toBe(3);
    });
});
