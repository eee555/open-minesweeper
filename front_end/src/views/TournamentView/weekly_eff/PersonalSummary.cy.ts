import PersonalSummary from './PersonalSummary.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { MS_Mode, MS_State } from '@/utils/ms_const';
import { VideoAbstract } from '@/utils/videoabstract';

describe('<Efficiency Weekly PersonalSummary />', () => {
    it('shows metric scores in two columns and excludes nonofficial and unsupported videos', () => {
        const video = (id: number, level: 'i' | 'e', timems: number) => new VideoAbstract({ id, level, timems, cl: 4, bv: 8, mode: MS_Mode.Standard, state: MS_State.Official, software: 'e' });
        const rejected = video(3, 'i', 1);
        rejected.state = MS_State.Frozen;
        cy.mount(PersonalSummary, { props: { videos: [video(1, 'i', 90000), video(2, 'e', 180000), rejected] }, global: { plugins: [i18n], config: { globalProperties: { $axios } }, stubs: { VideoPreviewLink: true } } });
        cy.get('[data-cy=weekly-eff-personal-total]').should('contain.text', '547.500');
        cy.get('[data-cy=weekly-eff-personal-summary] tbody').extractTableData().should((rows) => {
            expect(rows).to.have.length(5);
            expect(rows[2][0]).to.equal('60.000');
            expect(rows[2][1]).to.contain('262.500');
            expect(rows[3][1]).to.contain('285.000');
            expect(rows[4][1]).to.contain('547.500');
        });
    });
});
