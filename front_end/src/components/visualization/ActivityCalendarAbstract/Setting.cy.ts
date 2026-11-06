import Setting from './Setting.vue';

import i18n from '@/i18n';
import { activityCalendarConfig } from '@/store';

describe('<ActivityCalendar settings />', () => {
    const original = { ...activityCalendarConfig.value };

    beforeEach(() => {
        Object.assign(activityCalendarConfig.value, { showDate: false, useEndTime: false });
    });

    afterEach(() => {
        Object.assign(activityCalendarConfig.value, original);
    });

    it('updates and persists the two independent options without changing calendar dimensions', () => {
        cy.mount(Setting, { global: { plugins: [i18n] } });
        cy.get('[data-cy=calendar-show-date] input').should('not.be.checked');
        cy.get('[data-cy=calendar-use-end-time] input').should('not.be.checked');
        cy.contains('label', 'Show Date').click();
        cy.get('[data-cy=calendar-show-date] input').should('be.checked');
        cy.get('[data-cy=calendar-use-end-time] input').should('not.be.checked').focus();
        cy.realPress('Space');
        cy.get('[data-cy=calendar-use-end-time] input').should('be.checked');
        cy.window().its('localStorage').invoke('getItem', 'activity-calendar-config').should((value: string | null) => {
            const settings = JSON.parse(value ?? '{}') as Record<string, unknown>;
            expect(settings).to.include({ ...original, showDate: true, useEndTime: true });
        });
        cy.then(() => {
            activityCalendarConfig.value.showDate = false;
        });
        cy.get('[data-cy=calendar-show-date] input').should('not.be.checked');
        cy.get('[data-cy=calendar-use-end-time] input').should('be.checked');
    });
});
