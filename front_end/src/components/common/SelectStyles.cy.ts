import '@/styles/vendors/element-plus-select.css';
import '@/styles/vendors/primevue-table.css';

import Aura from '@primeuix/themes/aura';
import { ElOption, ElPagination, ElSelect } from 'element-plus';
import PrColumn from 'primevue/column';
import PrimeVue from 'primevue/config';
import PrDataTable from 'primevue/datatable';
import { defineComponent, h, ref } from 'vue';
import type { VNode } from 'vue';

function mountControls(render: () => VNode) {
    cy.mount(defineComponent({ expose: [], render }), { global: { plugins: [[PrimeVue, { theme: { preset: Aura, options: { darkModeSelector: '.dark' } } }]] } });
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

    it('keeps both paginator page-size menus usable and themes the teleported PrimeVue menu', () => {
        const elRows = ref(10);
        const primeRows = ref(10);
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
            h(PrDataTable, { value: Array.from({ length: 25 }, (_, id) => ({ id })),
                paginator: true,
                rows: primeRows.value,
                'onUpdate:rows': (value: number) => {
                    primeRows.value = value;
                },
                rowsPerPageOptions: [10, 20] }, {
                default: () => h(PrColumn, { field: 'id', header: 'ID' }),
            }),
        ]));
        matchesNative('.el-pagination .el-select__wrapper');
        matchesNative('.p-paginator-rpp-dropdown');
        cy.get('.el-pagination .el-select').click();
        cy.contains('.el-select-dropdown__item:visible', '20').click();
        cy.then(() => expect(elRows.value).to.equal(20));
        cy.get('.p-datatable-tbody tr').should('have.length', 10);
        cy.get('.p-paginator-rpp-dropdown').click();
        cy.get('.p-select-overlay').should('be.visible').and('have.css', 'border-radius', '0px');
        for (const dark of [false, true]) {
            cy.document().then((document) => document.documentElement.classList.toggle('dark', dark));
            cy.get('[data-cy=overlay-reference]').then(($reference) => {
                const expected = getComputedStyle($reference[0]);
                cy.get('.p-select-overlay').should('have.css', 'background-color', expected.backgroundColor).and('have.css', 'color', expected.color);
            });
        }
        cy.contains('.p-select-overlay .p-select-option', /^20$/).click();
        cy.get('.p-datatable-tbody tr').should('have.length', 20);
        cy.shouldBeAbsentOrHidden('.p-select-overlay');
        cy.get('.p-paginator-rpp-dropdown').click();
        cy.get('.p-paginator-rpp-dropdown [role=combobox]').should('be.focused').and('have.attr', 'aria-expanded', 'true');
        cy.get('.p-select-overlay').should('be.visible');
        cy.realPress('ArrowUp');
        cy.contains('.p-select-overlay .p-select-option', /^10$/).should('have.class', 'p-focus');
        cy.realPress('Enter');
        cy.get('.p-datatable-tbody tr').should('have.length', 10);
    });
});
