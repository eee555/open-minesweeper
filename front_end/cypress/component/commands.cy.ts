/* eslint-disable vue/one-component-per-file -- Each test mounts its own render-only fixture. */
import { ElNotification } from 'element-plus';
import { defineComponent, h, onMounted, ref } from 'vue';

describe('closeElNotifications', () => {
    afterEach(() => {
        ElNotification.closeAll();
    });

    for (const count of [0, 3]) {
        it(`closes ${count} persistent notifications without requiring a close button to exist`, () => {
            // Element Plus removes notifications in Transition hooks, which the default stub skips.
            cy.mount(defineComponent({
                expose: [],
                setup() {
                    onMounted(() => {
                        for (let index = 0; index < count; index++) {
                            ElNotification({ title: `Notice ${index + 1}`, duration: 0 });
                        }
                    });
                    return () => h('div');
                },
            }), { global: { stubs: { transition: false } } });

            cy.get('body').find('.el-notification:visible').should('have.length', count);
            cy.closeElNotifications();
            cy.get('.el-notification').should('not.exist');
            cy.closeElNotifications();
        });
    }
});

describe('extractTableData', () => {
    for (const target of ['table', 'tbody']) {
        it(`retries ${target} reads after Vue ${target === 'table' ? 'updates the cells' : 'replaces the table'}`, () => {
            const score = ref('--');
            let retried = false;
            cy.mount(defineComponent({
                expose: [],
                render: () => h('table', { key: target === 'tbody' ? score.value : 'stable', 'data-cy': 'async-table' }, [
                    h('thead', [h('tr', [h('th', 'Score')])]),
                    h('tbody', [h('tr', [h('td', score.value)])]),
                ]),
            }));

            cy.then(() => {
                // Update only after the first failed read; a frozen snapshot must not pass.
                cy.once('command:retry', () => {
                    retried = true;
                    score.value = '1.500(2)';
                });
            });
            const selector = target === 'table' ? '[data-cy=async-table]' : '[data-cy=async-table] tbody';
            const expected = target === 'table' ? [['Score'], ['1.500(2)']] : [['1.500(2)']];
            cy.get(selector).extractTableData().should('deep.equal', expected);
            cy.then(() => {
                expect(retried, 'assertion retried after reading the placeholder').to.equal(true);
            });
        });
    }
});

describe('shouldBeAbsentOrHidden', () => {
    it('accepts missing elements without waiting for them to exist', () => {
        cy.mount(defineComponent({
            expose: [],
            render: () => h('div'),
        }));

        cy.shouldBeAbsentOrHidden('[data-cy=missing]', { timeout: 0 });
    });

    it('accepts all matching elements hidden by their own styles or an ancestor', () => {
        cy.mount(defineComponent({
            expose: [],
            render: () => h('div', [
                h('span', { 'data-cy': 'hidden', style: 'display: none;' }, 'Display'),
                h('span', { 'data-cy': 'hidden', style: 'visibility: hidden;' }, 'Visibility'),
                h('span', { 'data-cy': 'hidden', style: 'opacity: 0;' }, 'Opacity'),
                h('div', { style: 'display: none;' }, [h('span', { 'data-cy': 'hidden' }, 'Ancestor')]),
            ]),
        }));

        cy.get('[data-cy=hidden]').should('have.length', 4);
        cy.shouldBeAbsentOrHidden('[data-cy=hidden]', { timeout: 0 });
    });

    for (const mode of ['hide', 'remove']) {
        it(`retries while any matching element is visible until it can ${mode}`, () => {
            const visible = ref(true);
            let retried = false;
            cy.mount(defineComponent({
                expose: [],
                render: () => h('div', [
                    h('span', { 'data-cy': 'target', style: 'display: none;' }, 'Already hidden'),
                    mode === 'remove' && !visible.value
                        ? null
                        : h('span', { 'data-cy': 'target', style: visible.value ? '' : 'display: none;' }, 'Initially visible'),
                ]),
            }));

            cy.contains('span', 'Initially visible').should('be.visible');
            cy.then(() => {
                // Change the fixture only after the command rejects the mixed hidden/visible set.
                cy.on('command:retry', () => {
                    retried = true;
                    visible.value = false;
                });
            });
            cy.shouldBeAbsentOrHidden('[data-cy=target]');
            cy.then(() => {
                expect(retried, 'did not accept a visible match').to.equal(true);
            });
            if (mode === 'remove') {
                cy.contains('span', 'Initially visible').should('not.exist');
            } else {
                cy.contains('span', 'Initially visible').should('not.be.visible');
            }
        });
    }
});
