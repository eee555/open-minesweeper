import { defineComponent, h } from 'vue';

import PlayerBadge from './PlayerBadge.vue';

import i18n from '@/i18n';
import { local } from '@/store/local';

describe('<PlayerBadge settings />', () => {
    const originalNameFormat = local.value.nameFormat;

    beforeEach(() => {
        local.value.nameFormat = 'first-last';
    });

    afterEach(() => {
        local.value.nameFormat = originalNameFormat;
    });

    it('selects and persists the name order with labels and native keyboard navigation', () => {
        cy.mount(PlayerBadge, { global: { plugins: [i18n] } });
        cy.get('[data-cy=player-name-order]').should('have.attr', 'role', 'radiogroup').and('have.attr', 'aria-label', 'International name format');
        cy.get('[data-cy=player-name-order] input[value=first-last]').should('be.checked');
        cy.contains('[data-cy=player-name-order] label', 'Family, Given').realClick();
        cy.get('[data-cy=player-name-order] input:checked').should('have.length', 1).and('have.value', 'last-first');
        cy.window().its('localStorage').invoke('getItem', 'local').should((value: string | null) => {
            expect(JSON.parse(value ?? '{}')).to.include({ nameFormat: 'last-first' });
        });

        cy.realPress('ArrowLeft');
        cy.get('[data-cy=player-name-order] input[value=first-last]').should('be.checked').and('be.focused');
        cy.realPress('Space');
        cy.get('[data-cy=player-name-order] input:checked').should('have.length', 1).and('have.value', 'first-last');
        cy.then(() => {
            local.value.nameFormat = 'last-first';
        });
        cy.get('[data-cy=player-name-order] input[value=last-first]').should('be.checked');
    });

    it('uses independent radio names for multiple instances while sharing the preference', () => {
        cy.mount(defineComponent({ expose: [], render: () => h('div', [h(PlayerBadge), h(PlayerBadge)]) }), { global: { plugins: [i18n] } });
        cy.get('[data-cy=player-name-order]').should('have.length', 2).then(($groups) => {
            const names = [...$groups].map((group) => [...group.querySelectorAll<HTMLInputElement>('input[type=radio]')].map((input) => input.name));
            expect(new Set(names[0]).size).to.equal(1);
            expect(new Set(names[1]).size).to.equal(1);
            expect(names[0][0]).not.to.equal(names[1][0]);
        });
        cy.get('[data-cy=player-name-order] input[value=first-last]:checked').should('have.length', 2);
        cy.get('[data-cy=player-name-order]').first().contains('label', 'Family, Given').click();
        cy.get('[data-cy=player-name-order] input[value=last-first]:checked').should('have.length', 2);
    });
});
