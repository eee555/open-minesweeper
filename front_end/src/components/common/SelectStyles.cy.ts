import '@/styles/vendors/element-plus-select.css';

import { ElOption, ElPagination, ElSelect } from 'element-plus';
import { defineComponent, h, ref } from 'vue';
import type { VNode } from 'vue';

function mountControls(render: () => VNode) {
    cy.mount(defineComponent({ expose: [], render }));
}

function matchesNative(control: string) {
    cy.get('[data-cy=native-select]').then(($native) => {
        const native = getComputedStyle($native[0]);
        const expected = { fontSize: native.fontSize, minHeight: native.minHeight, borderRadius: native.borderRadius, backgroundColor: native.backgroundColor };
        cy.get(control).should(($control) => {
            const actual = getComputedStyle($control[0]);
            for (const key of ['fontSize', 'minHeight', 'borderRadius', 'backgroundColor'] as const) expect(actual[key], key).to.equal(expected[key]);
        });
    });
}

describe('retained Select styles and interactions', () => {
    afterEach(() => {
        cy.document().then((document) => {
            document.documentElement.classList.remove('dark');
        });
    });

    for (const dark of [false, true]) {
        it(`keeps collapsed and wrapping tags, search, clear and disabled behavior usable in the ${dark ? 'dark' : 'light'} theme`, () => {
            const selected = ref(['', 'id-1', 'id-2']);
            const collapsed = ref(true);
            const disabled = ref(false);
            cy.document().then((document) => document.documentElement.classList.toggle('dark', dark));
            mountControls(() => h('div', { style: { width: '180px' } }, [
                h('select', { class: 'base-select base-select--small', 'data-cy': 'native-select', 'aria-label': 'Native reference' }, [h('option', 'Native')]),
                h(ElSelect, { modelValue: selected.value,
                    'onUpdate:modelValue': (value: string[]) => {
                        selected.value = value;
                    },
                    multiple: true,
                    filterable: true,
                    clearable: true,
                    collapseTags: collapsed.value,
                    disabled: disabled.value,
                    size: 'small',
                    ariaLabel: 'Identifiers' }, {
                    default: () => [
                        h(ElOption, { value: '', label: 'Empty identifier' }),
                        ...Array.from({ length: 30 }, (_, index) => h(ElOption, { value: `id-${index}`, label: `Player identifier ${index}`, disabled: index === 29 })),
                    ],
                }),
            ]));
            matchesNative('.el-select__wrapper');
            cy.get('.el-select .el-tag').should('have.length', 2);
            cy.then(() => {
                collapsed.value = false;
            });
            cy.get('.el-select .el-tag').should('have.length', 3);
            cy.get('.el-select__wrapper').should(($wrapper) => {
                const bounds = $wrapper[0].getBoundingClientRect();
                expect(bounds.height).to.be.greaterThan(24);
                for (const tag of $wrapper[0].querySelectorAll('.el-tag')) {
                    const rect = tag.getBoundingClientRect();
                    expect(rect.left).to.be.at.least(bounds.left);
                    expect(rect.right).to.be.at.most(bounds.right);
                    expect(rect.bottom).to.be.at.most(bounds.bottom);
                }
            });
            // An idle multiple Select hides its search input behind the tags until activated.
            cy.get('.el-select__wrapper').click();
            cy.get('.el-select__input').should('be.focused').type('identifier 5');
            cy.contains('.el-select-dropdown__item:visible', 'Player identifier 5').click();
            cy.then(() => expect(selected.value).to.deep.equal(['', 'id-1', 'id-2', 'id-5']));
            cy.get('.el-select__input').type('{esc}');
            cy.get('.el-select__wrapper').should('have.css', 'box-shadow', 'none');
            cy.get('.el-select').trigger('mouseenter');
            cy.get('.el-select__clear').click();
            cy.then(() => expect(selected.value).to.deep.equal([]));
            cy.get('.el-select__input').type('identifier 29');
            cy.contains('.el-select-dropdown__item:visible', 'Player identifier 29').should('have.class', 'is-disabled');
            cy.get('.el-select__input').type('{esc}');
            cy.then(() => {
                disabled.value = true;
            });
            cy.get('.el-select__input').should('be.disabled');
            cy.get('.el-select__wrapper').should('have.class', 'is-disabled').and('have.css', 'box-shadow', 'none');
        });
    }

    it('keeps the Element Plus paginator page-size menu usable and themes its teleported menu', () => {
        const elRows = ref(10);
        mountControls(() => h('div', [
            h('select', { class: 'base-select', 'data-cy': 'native-select', 'aria-label': 'Native reference' }, [h('option', 'Native')]),
            h('div', { 'data-cy': 'overlay-reference', style: { backgroundColor: 'var(--ui-select-overlay-background)', color: 'var(--ui-select-color)' } }, 'Overlay reference'),
            h(ElPagination, { total: 25,
                pageSize: elRows.value,
                'onUpdate:pageSize': (value: number) => {
                    elRows.value = value;
                },
                pageSizes: [10, 20],
                layout: 'sizes, prev, pager, next' }),
        ]));
        matchesNative('.el-pagination .el-select__wrapper');
        cy.get('.el-pagination .el-select').click();
        cy.get('.el-select__popper:visible').should('have.css', 'border-radius', '0px');
        for (const dark of [false, true]) {
            cy.document().then((document) => document.documentElement.classList.toggle('dark', dark));
            cy.get('[data-cy=overlay-reference]').then(($reference) => {
                const expected = getComputedStyle($reference[0]);
                cy.get('.el-select__popper:visible').should('have.css', 'background-color', expected.backgroundColor).and('have.css', 'color', expected.color);
            });
        }
        cy.contains('.el-select-dropdown__item:visible', '20').click();
        cy.then(() => expect(elRows.value).to.equal(20));
        cy.shouldBeAbsentOrHidden('.el-select__popper');
        cy.get('.el-pagination .el-select').click();
        cy.contains('.el-select-dropdown__item:visible', '10').click();
        cy.then(() => expect(elRows.value).to.equal(10));
    });
});
