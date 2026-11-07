import { defineComponent, h, ref } from 'vue';

import BilibiliLink from './BilibiliLink.vue';
import DiscordLink from './DiscordLink.vue';
import MsgamesLink from './MsgamesLink.vue';
import QQLink from './QQLink.vue';
import SaoleiLink from './SaoleiLink.vue';
import WomLink from './WomLink.vue';

import { mountAccountLink } from '@/components/accountlinks/testUtils';

const forms = [
    { name: 'Saolei', component: SaoleiLink, validId: '123', label: 'Saolei.wang ID' },
    { name: 'MSGames', component: MsgamesLink, validId: '123', label: 'Authoritative Minesweeper ID' },
    { name: 'WoM', component: WomLink, validId: '123', label: 'Minesweeper.Online ID' },
    { name: 'Bilibili', component: BilibiliLink, validId: '123', label: 'Bilibili ID' },
    { name: 'QQ', component: QQLink, validId: '123', label: 'Tencent QQ ID' },
    { name: 'Discord', component: DiscordLink, validId: '18446744073709551615', label: 'Discord ID' },
];

describe('platform linking forms', () => {
    for (const { name, component, validId, label } of forms) {
        it(`${name} validates IDs, submits on Enter, blocks submission while sending and remains editable after failure`, () => {
            const identifier = ref('');
            const sending = ref(false);
            const error = ref('');
            const submit = cy.spy().as('submit');
            mountAccountLink(defineComponent({
                expose: [],
                setup: () => () => h(component, {
                    modelValue: identifier.value,
                    'onUpdate:modelValue': (value: string) => {
                        identifier.value = value;
                    },
                    sending: sending.value,
                    error: error.value,
                    onSubmit: submit,
                }),
            }));
            cy.get('input').should('have.attr', 'aria-label', label);
            cy.get('button[type=submit]').should('be.disabled');
            for (const invalid of ['0', '00123', '12.3', 'abc']) {
                cy.get('input').clear();
                cy.get('input').type(invalid);
                cy.get('button[type=submit]').should('be.disabled');
                cy.get('form').submit();
            }
            cy.get('@submit').should('not.have.been.called');
            cy.get('input').clear();
            cy.get('input').type(`${validId}{enter}`);
            cy.get('@submit').should('have.been.calledOnce');
            cy.get('input').should('have.value', validId);
            cy.then(() => {
                sending.value = true;
            });
            cy.get('input').should('be.disabled');
            cy.get('button[type=submit]').should('be.disabled').and('have.attr', 'aria-busy', 'true');
            cy.get('form').submit();
            cy.get('@submit').should('have.been.calledOnce');
            cy.then(() => {
                sending.value = false;
                error.value = 'Link failed. Retry.';
            });
            cy.get('[role=alert]').should('contain', 'Link failed. Retry.');
            cy.get('input').should('be.enabled').and('have.value', validId).clear();
            cy.get('input').type('456');
            cy.get('button[type=submit]').should('be.enabled').click();
            cy.get('@submit').should('have.been.calledTwice');
        });
    }
});
