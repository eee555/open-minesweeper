interface TouchPosition { x: number; y: number; onBoard: boolean }

/** Keep tracking every finger while scrolling only a lone board contact. */
export class SingleTouchScroll {
    private readonly contacts = new Map<number, TouchPosition>();

    public down(id: number, x: number, y: number, onBoard: boolean): void {
        this.contacts.set(id, { x, y, onBoard });
    }

    public move(id: number, x: number, y: number): { x: number; y: number } | null {
        const previous = this.contacts.get(id);
        if (previous === undefined) return null;
        this.contacts.set(id, { ...previous, x, y });
        if (this.contacts.size !== 1 || !previous.onBoard) return null;
        return { x: previous.x - x, y: previous.y - y };
    }

    public up(id: number): void {
        this.contacts.delete(id);
    }

    public reset(): void {
        this.contacts.clear();
    }
}

/** Chain unused movement through ordinary scrollable ancestors, up to the page. */
export function scrollTouchAncestors(surface: HTMLElement, x: number, y: number): void {
    const doc = surface.ownerDocument;
    for (let element = surface.parentElement; element !== null; element = element.parentElement) {
        const style = getComputedStyle(element);
        const isPage = element === doc.scrollingElement;
        const left = isPage || (/auto|scroll/).test(style.overflowX) ? x : 0;
        const top = isPage || (/auto|scroll/).test(style.overflowY) ? y : 0;
        if (left !== 0 || top !== 0) {
            const beforeX = element.scrollLeft;
            const beforeY = element.scrollTop;
            element.scrollBy({ left, top, behavior: 'instant' });
            x -= element.scrollLeft - beforeX;
            y -= element.scrollTop - beforeY;
        }
        if (element === doc.fullscreenElement || (x === 0 && y === 0)) break;
    }
}
