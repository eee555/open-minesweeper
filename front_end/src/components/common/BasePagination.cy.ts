import { defineComponent, h, ref } from 'vue';

import BasePagination from './BasePagination.vue';
import type { PaginationRange } from './pagination';

import i18n from '@/i18n';

interface MountOptions {
    total?: number;
    currentStart?: number;
    pageSize?: number;
    pageSizeOptions?: number[];
    disabled?: boolean;
    width?: number;
}

function mountPagination(options: MountOptions = {}) {
    const total = ref<number>(options.total ?? 100);
    const currentStart = ref<number>(options.currentStart ?? 1);
    const pageSize = ref<number>(options.pageSize ?? 25);
    const changes: PaginationRange[] = [];
    cy.mount(defineComponent({
        expose: [],
        render: () => h('div', { style: `width: ${options.width ?? 700}px;` }, [
            h(BasePagination, {
                total: total.value,
                currentStart: currentStart.value,
                pageSize: pageSize.value,
                pageSizeOptions: options.pageSizeOptions,
                disabled: options.disabled,
                'onUpdate:currentStart': (value: number) => {
                    currentStart.value = value;
                },
                'onUpdate:pageSize': (value: number) => {
                    pageSize.value = value;
                },
                onChange: (range: PaginationRange) => {
                    changes.push(range);
                },
            }),
        ]),
    }), { global: { plugins: [i18n] } });
    return { total, currentStart, pageSize, changes };
}

function expectChanges(changes: PaginationRange[], expected: PaginationRange[]) {
    cy.then(() => {
        expect(changes).to.deep.equal(expected);
    });
}

function typeJump(value: string) {
    cy.get('[data-cy=jump]').clear();
    cy.get('[data-cy=jump]').type(value);
}

describe('<BasePagination />', () => {
    it('renders intervals, moves by page size and emits one change per action', () => {
        const { currentStart, changes } = mountPagination({ total: 100 });
        cy.get('[data-cy=nav-buttons]').children().then(($children) => {
            expect($children.eq(0).attr('data-cy')).to.equal('prev');
            expect($children.eq(1).attr('data-cy')).to.equal('next');
        });
        cy.get('[data-cy=report]').should('have.text', '1-25 / 100');
        cy.get('[data-cy=segment]').should('have.length', 4);
        cy.get('[data-cy=segment]').first().should('have.attr', 'aria-current', 'page');
        cy.get('[data-cy=next]').click();
        cy.get('[data-cy=report]').should('have.text', '26-50 / 100');
        cy.contains('[data-cy=segment]', '76-100').click();
        cy.get('[data-cy=report]').should('have.text', '76-100 / 100');
        cy.get('[data-cy=next]').should('be.disabled');
        cy.get('[data-cy=prev]').click();
        cy.get('[data-cy=report]').should('have.text', '51-75 / 100');
        cy.contains('[data-cy=segment]', '1-25').click();
        cy.get('[data-cy=report]').should('have.text', '1-25 / 100');
        cy.get('[data-cy=prev]').should('be.disabled');
        cy.then(() => {
            expect(currentStart.value).to.equal(1);
        });
        expectChanges(changes, [
            { start: 26, end: 50 },
            { start: 76, end: 100 },
            { start: 51, end: 75 },
            { start: 1, end: 25 },
        ]);
    });

    it('limits interval buttons for large totals and truncates the last interval', () => {
        const { changes } = mountPagination({ total: 1000, currentStart: 501 });
        cy.get('[data-cy=segment]').should('have.length', 7);
        cy.get('.base-pagination__ellipsis').should('have.length', 2);
        cy.get('[data-cy=segment]').last().invoke('text').should('contain', '976-1000');
        cy.get('[data-cy=segment]').then(($buttons) => {
            const current = [...$buttons].filter((button) => button.getAttribute('aria-current') === 'page');
            expect(current).to.have.length(1);
            expect(current[0]?.textContent?.trim()).to.equal('501-525');
        });
        cy.contains('[data-cy=segment]', '476-500').click();
        cy.get('[data-cy=report]').should('have.text', '476-500 / 1000');
        expectChanges(changes, [{ start: 476, end: 500 }]);
    });

    it('jumps to an arbitrary start index and shows it as the current interval', () => {
        const { currentStart, changes } = mountPagination({ total: 37 });
        typeJump('13{enter}');
        cy.get('[data-cy=report]').should('have.text', '13-37 / 37');
        cy.get('[data-cy=segment]').then(($buttons) => {
            const current = [...$buttons].filter((button) => button.getAttribute('aria-current') === 'page');
            expect(current).to.have.length(1);
            expect(current[0]?.textContent?.trim()).to.equal('13-37');
        });
        cy.get('[data-cy=jump]').blur();
        cy.then(() => {
            expect(currentStart.value).to.equal(13);
        });
        expectChanges(changes, [{ start: 13, end: 37 }]);
    });

    it('restores invalid jump input, ignores a no-op jump and clamps an out-of-range index', () => {
        const { changes, currentStart } = mountPagination({ total: 100 });
        typeJump('abc{enter}');
        cy.get('[data-cy=jump]').should('have.value', '1');
        typeJump('26{enter}');
        cy.get('[data-cy=report]').should('have.text', '26-50 / 100');
        typeJump('26{enter}');
        typeJump('999{enter}');
        cy.get('[data-cy=report]').should('have.text', '100-100 / 100');
        cy.then(() => {
            expect(currentStart.value).to.equal(100);
        });
        expectChanges(changes, [{ start: 26, end: 50 }, { start: 100, end: 100 }]);
    });

    it('resets the start index when the page size changes and keeps an unlisted size visible', () => {
        const { changes, currentStart, pageSize } = mountPagination({ total: 100, pageSize: 7, pageSizeOptions: [5, 10, 25] });
        cy.get('[data-cy=page-size]').should('have.value', '7');
        cy.get('[data-cy=page-size] option').should('have.length', 4);
        typeJump('50{enter}');
        cy.get('[data-cy=report]').should('have.text', '50-56 / 100');
        cy.get('[data-cy=page-size]').select('10');
        cy.get('[data-cy=report]').should('have.text', '1-10 / 100');
        cy.then(() => {
            expect(currentStart.value).to.equal(1);
            expect(pageSize.value).to.equal(10);
        });
        expectChanges(changes, [{ start: 50, end: 56 }, { start: 1, end: 10 }]);
    });

    it('keeps the start sentinel for an empty result without navigation or jumps', () => {
        const { changes, currentStart } = mountPagination({ total: 0, currentStart: 50 });
        cy.get('[data-cy=report]').should('have.text', '0-0 / 0');
        cy.get('[data-cy=segment]').should('not.exist');
        cy.get('[data-cy=prev]').should('be.disabled');
        cy.get('[data-cy=next]').should('be.disabled');
        cy.get('[data-cy=jump]').should('be.disabled');
        cy.then(() => {
            expect(currentStart.value).to.equal(1);
        });
        expectChanges(changes, []);
    });

    it('clamps an out-of-range model and a shrinking total without user change events', () => {
        const { changes, currentStart, total } = mountPagination({ total: 100, currentStart: 76 });
        cy.get('[data-cy=report]').should('have.text', '76-100 / 100');
        cy.then(() => {
            total.value = 30;
            currentStart.value = 99;
        });
        cy.get('[data-cy=report]').should('have.text', '30-30 / 30');
        cy.then(() => {
            expect(currentStart.value).to.equal(30);
        });
        expectChanges(changes, []);
    });

    it('disables every control while keeping the report visible', () => {
        const { changes } = mountPagination({ total: 100, disabled: true });
        cy.get('[data-cy=prev]').should('be.disabled');
        cy.get('[data-cy=next]').should('be.disabled');
        cy.get('[data-cy=segment]').first().should('be.disabled');
        cy.get('[data-cy=page-size]').should('be.disabled');
        cy.get('[data-cy=jump]').should('be.disabled');
        cy.get('[data-cy=report]').should('be.visible');
        expectChanges(changes, []);
    });

    it('adjusts interval buttons as the container resizes', () => {
        const start = ref<number>(501);
        const width = ref<number>(700);
        cy.mount(defineComponent({
            expose: [],
            render: () => h('div', { style: `width: ${width.value}px;` }, [
                h(BasePagination, {
                    total: 1000,
                    currentStart: start.value,
                    'onUpdate:currentStart': (value: number) => {
                        start.value = value;
                    },
                }),
            ]),
        }), { global: { plugins: [i18n] } });
        cy.get('[data-cy=segment]').should('have.length', 7);
        cy.then(() => {
            width.value = 300;
        });
        cy.get('[data-cy=segment]').should('have.length', 3);
        cy.get('.base-pagination__ellipsis').should('have.length', 2);
        cy.then(() => {
            width.value = 1920;
        });
        cy.get('[data-cy=segment]').should(($buttons) => {
            expect($buttons.length).to.be.greaterThan(7);
        });
    });

    it('lets control groups wrap inside a narrow container', () => {
        const start = ref<number>(1);
        cy.mount(defineComponent({
            expose: [],
            render: () => h('div', { style: 'width: 200px;' }, [
                h(BasePagination, {
                    total: 1000,
                    currentStart: start.value,
                    'onUpdate:currentStart': (value: number) => {
                        start.value = value;
                    },
                }),
            ]),
        }), { global: { plugins: [i18n] } });
        cy.get('.base-pagination').should('have.css', 'flex-wrap', 'wrap');
        cy.get('.base-pagination__group').first().should('have.css', 'flex-wrap', 'wrap');
    });
});
