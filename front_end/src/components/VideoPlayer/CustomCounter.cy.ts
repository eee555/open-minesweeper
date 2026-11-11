import { nextTick } from 'vue';

import CustomCounter from './CustomCounter.vue';
import type { CustomCounterConfig, CustomCounterTableRow } from './types';

import type { AnyVideo } from '@/utils/fileIO';

function createVideo(values: Record<string, unknown>) {
    return values as unknown as AnyVideo;
}

function counterCell(label: string) {
    return cy.contains('.custom-counter-wrap th', new RegExp(`^${label}$`)).next('td');
}

function createConfig(table: CustomCounterTableRow[]): CustomCounterConfig {
    return {
        table,
        thWidth: 90,
        tdWidth: 130,
        fontSize: 12,
    };
}

function mountCustomCounter(video: AnyVideo, table: CustomCounterTableRow[], currentMs = 0) {
    cy.mount(CustomCounter, {
        props: {
            video,
            currentMs,
            config: createConfig(table),
        },
    });
}

describe('<CustomCounter />', () => {
    it('renders custom expression rows', () => {
        mountCustomCounter(createVideo({
            bbbv: 24,
            bbbv_s: 3.456,
            bbbv_solved: 12,
            cl: 4,
            double: 1,
            left: 2,
            right: 1,
        }), [
            ['bvs', 'roundTo(bbbv_s, 2) || "@" || bbbv_solved || "/" || bbbv'],
            ['cl', 'cl || "=" || left || "+" || right || "+" || double'],
        ]);

        cy.get('.custom-counter-wrap').should('be.visible');
        counterCell('bvs').should('have.text', '3.46@12/24');
        counterCell('cl').should('have.text', '4=2+1+1');
    });

    it('shows expression errors directly in the value cell', () => {
        mountCustomCounter(createVideo({ bbbv: 24 }), [
            ['bad', 'unknown_key + 1'],
        ]);

        counterCell('bad').should('have.class', 'custom-counter__value--error').and('contain', 'Unknown variable: unknown_key');
    });

    it('pads fixed decimals, keeps roundTo numeric, and updates fixed-width text with playback', () => {
        const values = { bbbv_s: 3.4 };
        mountCustomCounter(createVideo(values), [
            ['fixed', 'toFixed(bbbv_s, 3)'],
            ['rounded', 'roundTo(bbbv_s, 3)'],
            ['combined', 'toFixed(bbbv_s, 2) || "x"'],
            ['integer', 'toFixed(3.6, 0)'],
            ['badPrecision', 'toFixed(bbbv_s, 101)'],
        ]);
        counterCell('fixed').should('have.text', '3.400');
        counterCell('rounded').should('have.text', '3.4');
        counterCell('combined').should('have.text', '3.40x');
        counterCell('integer').should('have.text', '4');
        counterCell('badPrecision').should('have.class', 'custom-counter__value--error');
        cy.get('@vue').then((wrapper: ComponentWrapper<typeof CustomCounter>) => {
            values.bbbv_s = 3;
            return wrapper.setProps({ currentMs: 100 });
        });
        counterCell('fixed').should('have.text', '3.000');
        counterCell('rounded').should('have.text', '3');
        counterCell('combined').should('have.text', '3.00x');
    });

    it('keeps long rendered values constrained by cell overflow styles', () => {
        mountCustomCounter(createVideo({}), [
            ['long', '"*" || roundTo'],
        ]);

        counterCell('long').should('contain', 'function');
        counterCell('long').should('have.css', 'overflow', 'hidden');
        counterCell('long').should('have.css', 'text-overflow', 'ellipsis');
        counterCell('long').should('have.css', 'white-space', 'nowrap');
        counterCell('long').invoke('outerWidth').should('be.lte', 130);
    });

    it('refreshes when currentMs changes', () => {
        const videoValues = { bbbv_solved: 1 };
        mountCustomCounter(createVideo(videoValues), [['solved', 'bbbv_solved']], 0);

        counterCell('solved').should('have.text', '1');
        cy.get('@vue').then((wrapper: ComponentWrapper<typeof CustomCounter>) => {
            videoValues.bbbv_solved = 2;
            return wrapper.setProps({ currentMs: 100 }).then(() => nextTick());
        });
        counterCell('solved').should('have.text', '2');
    });

    it('renders two label/value pairs per row in double-column layout', () => {
        cy.mount(CustomCounter, {
            props: {
                video: createVideo({}),
                currentMs: 0,
                config: createConfig([
                    ['a', '1'],
                    ['b', '2'],
                    ['c', '3'],
                    ['d', '4'],
                    ['e', '5'],
                ]),
                doubleColumn: true,
            },
        });

        cy.get('.custom-counter colgroup col').should('have.length', 4);
        cy.get('.custom-counter tbody tr').should('have.length', 3);
        cy.get('.custom-counter tbody tr').first().find('th, td').should('have.length', 4);
        cy.get('.custom-counter tbody tr').last().find('th, td').should('have.length', 4);
        cy.get('.custom-counter tbody tr').first().find('th').then(($labels) => {
            expect(Array.from($labels, (element) => element.textContent?.trim())).to.deep.equal(['a', 'd']);
        });
        counterCell('e').should('have.text', '5');
    });
});
