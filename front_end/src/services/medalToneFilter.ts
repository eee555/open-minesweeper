import { softMetalToneTable } from './medalMaterial';

const entries = new Map<string, { element: SVGElement; references: number }>();
const namespace = 'http://www.w3.org/2000/svg';
function element(name: string, attributes: Record<string, string>): SVGElement {
    const result = document.createElementNS(namespace, name);
    for (const [key, value] of Object.entries(attributes)) result.setAttribute(key, value);
    return result;
}

/** Share each active color and keep at most 32 unused drag-preview filters. */
export function acquireMedalToneFilter(color: string): { filter: string; release: () => void } {
    const id = 'medal-soft-' + color.slice(1).toLowerCase();
    let entry = entries.get(id);
    if (entry?.element.isConnected !== true) {
        let definitions: Element | null = document.getElementById('medal-tone-definitions');
        if (!definitions) {
            const root = element('svg', { width: '0', height: '0', 'aria-hidden': 'true', focusable: 'false', style: 'position:absolute;overflow:hidden;pointer-events:none' });
            definitions = element('defs', { id: 'medal-tone-definitions' });
            root.append(definitions); document.body.append(root);
        }
        const filter = element('filter', { id, 'color-interpolation-filters': 'sRGB' });
        filter.append(element('feColorMatrix', { type: 'saturate', values: '0' }));
        const transfer = element('feComponentTransfer', {});
        for (const [index, channel] of ['R', 'G', 'B'].entries()) {
            const value = parseInt(color.slice(1 + index * 2, 3 + index * 2), 16) / 255;
            transfer.append(element('feFunc' + channel, { type: 'table', tableValues: softMetalToneTable(value).map((v) => v.toFixed(6)).join(' ') }));
        }
        filter.append(transfer); definitions.append(filter);
        entry = { element: filter, references: 0 }; entries.set(id, entry);
    }
    entry.references += 1;
    const acquired = entry;
    return { filter: `url(#${id})`,
        release: () => {
            acquired.references -= 1;
            const unused = [...entries].filter(([, value]) => value.references === 0);
            for (const [key, value] of unused.slice(0, Math.max(0, unused.length - 32))) {
                value.element.remove(); entries.delete(key);
            }
        } };
}
