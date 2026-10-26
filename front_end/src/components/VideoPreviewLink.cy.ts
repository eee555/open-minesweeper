import { defineComponent, h } from 'vue';

import VideoPreviewLink from './VideoPreviewLink.vue';

import i18n from '@/i18n';
import { videoplayerstore } from '@/store';
import { local } from '@/store/local';
import type { MS_Software } from '@/utils/ms_const';
import { VideoAbstract } from '@/utils/videoabstract';
import { mockVideoInfo } from '@cy/support/videoInfo';

function mountLink(id: number | null | undefined, software?: MS_Software, showTooltip = true) {
    const video = software !== undefined && id != null && id > 0 ? new VideoAbstract({ id, software, level: 'b', mode: '00', timems: 12345, bv: 4, state: 'c' }) : undefined;
    cy.mount(defineComponent({
        expose: [],
        render: () => h(VideoPreviewLink, { id, software, video, showTooltip }, () => '12.345'),
    }), { global: { plugins: [i18n] } });
}

describe('<VideoPreviewLink />', () => {
    beforeEach(() => {
        videoplayerstore.visible = false;
    });

    afterEach(() => {
        videoplayerstore.visible = false;
        Reflect.deleteProperty(local.value, 'tooltip_show');
    });

    it('opens the existing player by keyboard without navigating away', () => {
        mockVideoInfo([{ id: 42, software: 'e' }], 'software');
        mountLink(42);

        cy.get('.video-preview-link').should('have.attr', 'href', '#/video/42').focus();
        cy.realPress('Enter');
        cy.wait('@parsedVideoInfo').its('request.query.ids').should('eq', '42');
        cy.wrap(videoplayerstore).its('visible').should('eq', true);
        cy.wrap(videoplayerstore).its('id').should('eq', 42);
        cy.wrap(videoplayerstore).its('url').should('include', '/api/video/preview?id=42');
        cy.location('hash').should('not.eq', '#/video/42');
        cy.get('@software.all').should('have.length', 0);
        cy.get('@parsedVideoInfo.all').should('have.length', 1);
    });

    it('opens the preview once on an ordinary click and reuses a supplied video without downloading it', () => {
        mockVideoInfo([{ id: 42, software: 'e' }], 'software');
        mountLink(43, 'r');
        const parentClick = cy.spy().as('parentClick');
        cy.get('.video-preview-link').then(($link) => {
            $link[0].parentElement?.addEventListener('click', () => {
                parentClick();
            });
        }).click();

        cy.wrap(videoplayerstore).its('visible').should('eq', true);
        cy.wrap(videoplayerstore).its('url').should('include', '/api/video/preview?id=43.rmv');
        cy.location('hash').should('not.eq', '#/video/43');
        cy.get('@software.all').should('have.length', 0);
        cy.get('@parsedVideoInfo.all').should('have.length', 0);
        cy.get('@parentClick').should('not.have.been.called');
    });

    it('loads the software icon and renders a single summary on hover without opening the player', () => {
        mockVideoInfo([{ id: 42, software: 'a', timems: 12345, bv: 4 }]);
        mountLink(42);
        cy.get('.video-preview-link .video-preview-software').should('be.visible').and('have.attr', 'title', i18n.global.t('common.software.a'));
        cy.get('.descriptions').should('not.exist');
        cy.get('.video-preview-link').trigger('mouseenter');
        cy.get('[role=tooltip]:visible').should('have.length', 1).and('contain.text', '12.345').and('not.contain.text', i18n.global.t('common.prop.upload_time'));
        cy.wrap(videoplayerstore).its('visible').should('eq', false);
        cy.get('.video-preview-link').trigger('mouseleave');
        cy.get('[role=tooltip]:visible').should('not.exist');
        cy.get('@videoMetadata.all').should('have.length', 0);
        cy.get('@parsedVideoInfo.all').should('have.length', 1);
    });

    it('shows the summary and software name even when a retired help preference is disabled', () => {
        Reflect.set(local.value, 'tooltip_show', false);
        mountLink(43, 'r');

        cy.get('.video-preview-software').should('have.attr', 'title', i18n.global.t('common.software.r'));
        cy.get('.video-preview-link').trigger('mouseenter');
        cy.get('[role=tooltip]:visible').should('have.length', 1).and('contain.text', '12.345');
        cy.wrap(videoplayerstore).its('visible').should('eq', false);
        cy.get('.video-preview-link').trigger('mouseleave');
        cy.get('[role=tooltip]:visible').should('not.exist');
    });

    it('keeps the per-link summary opt-out', () => {
        mountLink(43, 'r', false);

        cy.get('.video-preview-link').trigger('mouseenter');
        cy.get('[role=tooltip]:visible').should('not.exist');
        cy.get('.descriptions').should('not.exist');
    });

    it('discards late data after the linked video changes', () => {
        mockVideoInfo([{ id: 42, software: 'a' }, { id: 43, software: 'r' }]);
        let requested = false;
        cy.intercept('GET', '**/api/video/staticdetailbatch*', (request) => {
            requested = true;
            const id = Number(String(request.query.ids).split(',')[0]);
            request.reply({ delay: id === 42 ? 500 : 0, body: [{ id, software: id === 42 ? 'a' : 'r', ongoing_tournament: false }] });
        }).as('parsedVideoInfo');
        const Link = defineComponent({
            props: { id: { type: Number, default: 42 } },
            setup: (props) => () => h(VideoPreviewLink, { id: props.id }, () => '12.345'),
        });
        cy.mount(Link, { global: { plugins: [i18n] } });
        cy.wrap(null).should(() => {
            expect(requested).to.equal(true);
        });
        cy.get<ComponentWrapper<typeof Link>>('@vue').then((wrapper) => wrapper.setProps({ id: 43 }));
        cy.get('.video-preview-link').should('have.attr', 'href', '#/video/43');
        cy.get('.video-preview-software').should('have.attr', 'title', i18n.global.t('common.software.r'));
        cy.get('@videoMetadata.all').should('have.length', 0);
    });

    for (const options of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }]) {
        it(`preserves native navigation for ${JSON.stringify(options)} without opening the preview`, () => {
            mountLink(42, 'e');
            const parentClick = cy.spy().as('parentClick');
            cy.get('.video-preview-link').then(($link) => {
                const [link] = $link;
                const handleParentClick = () => {
                    parentClick();
                };
                link.parentElement?.addEventListener('click', handleParentClick);
                link.parentElement?.addEventListener('auxclick', handleParentClick);
                // Observe the component's handling, then prevent browser navigation in this test.
                link.addEventListener(options.button === 1 ? 'auxclick' : 'click', (event) => {
                    expect(event.defaultPrevented).to.equal(false);
                    event.preventDefault();
                }, { once: true });
                link.dispatchEvent(new MouseEvent(options.button === 1 ? 'auxclick' : 'click', { bubbles: true, cancelable: true, ...options }));
            });
            cy.wrap(videoplayerstore).its('visible').should('eq', false);
            cy.get('@parentClick').should('not.have.been.called');
        });
    }

    for (const id of [undefined, null, 0, -1]) {
        it(`renders a non-interactive placeholder for ID ${id}`, () => {
            mountLink(id);
            cy.contains('span', '--').should('be.visible');
            cy.get('.video-preview-link').should('not.exist');
            cy.wrap(videoplayerstore).its('visible').should('eq', false);
        });
    }
});
