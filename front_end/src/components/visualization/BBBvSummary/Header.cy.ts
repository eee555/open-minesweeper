import Header from './Header.vue';

import i18n from '@/i18n';
import { BBBvSummaryConfig } from '@/store';
import { pinia } from '@/store/create';

const mountHeader = () => {
    cy.mount(Header, {
        global: {
            plugins: [i18n, pinia],
        },
    });
};

describe('<BBBvSummary Header />', () => {
    beforeEach(() => {
        cy.clearLocalStorage('bbbv-summary-config');
        Object.assign(BBBvSummaryConfig.value, { template: 'time', sortBy: 'timems', displayBy: 'time', sortDesc: false, softwareFilter: ['e', 'a', 'r', 'm'], zoom: 1, showIcon: 'software', newThresh: 1, newDateField: 'upload_time' });
    });

    it('persists template changes and exposes custom sorting controls', () => {
        mountHeader();

        cy.get('.el-select').first().click();
        cy.contains('.el-select-dropdown__item', 'Custom').click();

        cy.contains('Find min').should('be.visible');
        cy.contains('and display by').should('be.visible');
        cy.wrap(BBBvSummaryConfig).its('value.template').should('eq', 'custom');

        cy.contains('button', 'Find min').focus();
        cy.realPress('Space');
        cy.contains('Find max').should('be.visible');
        cy.wrap(BBBvSummaryConfig).its('value.sortDesc').should('eq', true);

        cy.get('.el-select').eq(1).click();
        cy.get('.el-select-dropdown:visible').contains('IOE').click();
        cy.get('.el-select').eq(2).click();
        cy.get('.el-select-dropdown:visible').contains('File Size').click();

        cy.wrap(BBBvSummaryConfig).its('value.sortBy').should('eq', 'ioe');
        cy.wrap(BBBvSummaryConfig).its('value.displayBy').should('eq', 'file_size');
    });

    it('updates the software selection while keeping all software icons available', () => {
        BBBvSummaryConfig.value.softwareFilter = ['e', 'a', 'r', 'm'];
        mountHeader();
        cy.get('.checkbox-buttons--compact img').should('have.length', 5);
        cy.get('.checkbox-buttons--compact label').first().click();
        cy.wrap(BBBvSummaryConfig).its('value.softwareFilter').should('deep.equal', ['a', 'r', 'm']);
        cy.get('.checkbox-buttons--compact input[value=e]').should('not.be.checked').focus();
        cy.realPress('Space');
        cy.wrap(BBBvSummaryConfig).its('value.softwareFilter').should('deep.equal', ['a', 'r', 'm', 'e']);
    });

    it('persists icon mode, new highlight settings, and zoom', () => {
        mountHeader();

        cy.contains('Icon').next().click();
        cy.get('.el-select-dropdown:visible').contains('State').click();
        cy.wrap(BBBvSummaryConfig).its('value.showIcon').should('eq', 'state');

        cy.contains('uploaded').click();
        cy.wrap(BBBvSummaryConfig).its('value.newDateField').should('eq', 'end_time');

        cy.get('.el-input-number input').clear();
        cy.get('.el-input-number input').type('3');
        cy.get('.el-input-number input').blur();
        cy.wrap(BBBvSummaryConfig).its('value.newThresh').should('eq', 3);

        cy.get('[data-cy=zoomin]').click();
        cy.wrap(BBBvSummaryConfig).its('value.zoom').should('be.closeTo', 1.1, 0.001);
    });
});
