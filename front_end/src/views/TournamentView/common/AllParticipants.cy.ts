
import { defineComponent, h } from 'vue';
import type { Component, PropType } from 'vue';

import AllParticipants from './AllParticipants.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { pinia } from '@/store/create';
import { TournamentParticipant } from '@/utils/tournaments';
import type { VideoAbstract } from '@/utils/videoabstract';

type TestParticipant = TournamentParticipant & {
    name: string;
};

const participants: TestParticipant[] = [
    Object.assign(new TournamentParticipant({ id: 11, user_id: 101, tournament_id: 9001 }), { name: 'Alpha' }),
    Object.assign(new TournamentParticipant({ id: 22, user_id: 202, tournament_id: 9001 }), { name: 'Bravo' }),
    Object.assign(new TournamentParticipant({ id: 44, user_id: 0, tournament_id: 9001 }), { name: 'Zero' }),
];

const TypedAllParticipants = AllParticipants as unknown as Component;

interface AllSummarySlotProps {
    data: TestParticipant[];
    onParticipantSelect: (participant: TestParticipant) => void;
}

interface PersonalSummarySlotProps {
    videos: VideoAbstract[];
}

const TestHost = defineComponent({
    components: { AllParticipants: TypedAllParticipants },
    props: {
        result: {
            type: Array as PropType<TestParticipant[]>,
            required: true,
        },
    },
    expose: [],
    render() {
        return h(TypedAllParticipants, {
            result: this.result,
        }, {
            allSummary: ({ data, onParticipantSelect }: AllSummarySlotProps) => h('div', {}, data.map((participant) => h('button', {
                key: participant.id,
                'data-cy': `participant-${participant.id}`,
                onClick: () => {
                    onParticipantSelect(participant);
                },
            }, participant.name))),
            personalSummary: ({ videos }: PersonalSummarySlotProps) => h('div', { 'data-cy': 'personal-summary' }, `videos: ${videos.length}`),
        });
    },
});

const PersonalViewStub = defineComponent({
    props: {
        modelValue: { type: Object as PropType<TournamentParticipant>, required: true },
    },
    expose: [],
    render() {
        return h('section', { 'data-cy': 'personal-view' }, this.$slots.personalSummary?.({ videos: [] }));
    },
});

function mountAllParticipants(options: {
    result?: TestParticipant[];
} = {}) {
    cy.mockPlayerNameFallback();
    cy.mount(TestHost as never, {
        props: {
            result: options.result ?? participants,
        },
        global: {
            plugins: [pinia, i18n],
            config: { globalProperties: { $axios } },
            stubs: {
                PersonalView: PersonalViewStub,
            },
        },
    } as never);
}

function topLevelTabItems() {
    return cy.get('[data-cy=all-participants-tabs] > .el-tabs__header .el-tabs__item');
}

function topLevelTab(id: number) {
    return cy.get(`[id="tab-${id}"]`);
}

function activeTopLevelTabShouldBe(id: number) {
    cy.get('.el-tabs__item.is-active').should('have.attr', 'id', `tab-${id}`);
}

describe('<AllParticipants />', () => {
    it('opens participant tabs and reuses an existing tab', () => {
        mountAllParticipants();

        topLevelTabItems().should('have.length', 1);
        cy.get('[data-cy=participant-11]').click();
        topLevelTabItems().should('have.length', 2);
        activeTopLevelTabShouldBe(11);
        cy.get('[data-cy=personal-summary]').should('contain.text', 'videos: 0');

        topLevelTabItems().first().click();
        cy.get('[data-cy=participant-22]').click();
        topLevelTabItems().should('have.length', 3);
        activeTopLevelTabShouldBe(22);

        topLevelTabItems().first().click();
        cy.get('[data-cy=participant-11]').click();
        topLevelTabItems().should('have.length', 3);
        activeTopLevelTabShouldBe(11);

        topLevelTab(22).contains('User#202').click();
        activeTopLevelTabShouldBe(22);
        topLevelTab(11).contains('User#101').click();
        activeTopLevelTabShouldBe(11);
        cy.get('[id^=tippy-]').should('not.exist');
    });

    it('keeps the active participant tab when another tab is closed', () => {
        mountAllParticipants();

        cy.get('[data-cy=participant-11]').click();
        topLevelTabItems().first().click();
        cy.get('[data-cy=participant-22]').click();
        activeTopLevelTabShouldBe(22);

        topLevelTab(11).find('[data-cy=all-participants-tab-close]').focus();
        cy.realPress('Enter');
        topLevelTabItems().should('have.length', 2);
        topLevelTab(11).should('not.exist');
        activeTopLevelTabShouldBe(22);

        topLevelTab(22).find('[data-cy=all-participants-tab-close]').click();
        topLevelTabItems().should('have.length', 1);
        activeTopLevelTabShouldBe(-1);
        cy.get('[data-cy=personal-view]').should('not.exist');
    });

    it('does not open tabs for invalid participants', () => {
        mountAllParticipants();

        cy.get('[data-cy=participant-44]').click();
        topLevelTabItems().should('have.length', 1);

        cy.get('[data-cy=participant-11]').click();
        topLevelTabItems().should('have.length', 2);
        activeTopLevelTabShouldBe(11);
    });
});
