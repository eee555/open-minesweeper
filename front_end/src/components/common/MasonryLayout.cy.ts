import { MasonryGrid } from '@egjs/grid';
import type { PropType } from 'vue';
import { defineComponent, h } from 'vue';

import MasonryLayout from './MasonryLayout.vue';

const heights = [180, 80, 120, 60];

// Keep dimensions in Vue props so renderComplete updates cannot restore DOM-only style changes.
const LayoutFixture = defineComponent({
    props: {
        width: { type: Number, required: true },
        heights: { type: Array as PropType<number[]>, required: true },
        minimumColumnWidth: { type: Number, default: 304 },
    },
    setup: (props) => () => h(MasonryLayout, { minimumColumnWidth: props.minimumColumnWidth, style: { width: `${props.width}px` } }, {
        default: () => props.heights.map((height, index) => h('div', { 'data-item': index, style: { height: `${height}px` } }, `Card ${index}`)),
    }),
});

function mountLayout(width = 640) {
    cy.mount(LayoutFixture, { props: { width, heights } });
    cy.get('.masonry-layout').should(($layout) => {
        expect(Number($layout.attr('data-layout-version'))).to.be.greaterThan(0);
    });
}

describe('<MasonryLayout />', () => {
    it('packs different heights into aligned columns without row gaps or overlap', () => {
        mountLayout();
        cy.get('[data-item]').should(($items) => {
            const [first, second, third, fourth] = $items.toArray().map((element) => element.getBoundingClientRect());
            expect(first.width).to.be.closeTo(312, 0.5);
            expect(second.width).to.be.closeTo(first.width, 0.5);
            expect(first.top).to.be.closeTo(second.top, 0.5);
            expect(second.left - first.right).to.be.closeTo(16, 0.5);
            expect(third.left).to.be.closeTo(second.left, 0.5);
            expect(third.top - second.bottom).to.be.closeTo(16, 0.5);
            expect(fourth.left).to.be.closeTo(first.left, 0.5);
            expect(fourth.top - first.bottom).to.be.closeTo(16, 0.5);
            expect(third.top).to.be.lessThan(first.bottom);
        });
        cy.get('.masonry-layout').should(($layout) => {
            expect($layout[0].getBoundingClientRect().height).to.be.closeTo(256, 0.5);
        });
    });

    it('reflows when a card changes height without a window resize', () => {
        mountLayout();
        cy.get<ComponentWrapper<typeof LayoutFixture>>('@vue').then((wrapper) => wrapper.setProps({ heights: [180, 300, 120, 60] }));
        cy.get('[data-item="1"]').should('have.css', 'height', '300px');
        cy.get('[data-item]').should(($items) => {
            const [first, second, third, fourth] = $items.toArray().map((element) => element.getBoundingClientRect());
            expect(third.left).to.be.closeTo(first.left, 0.5);
            expect(third.top - first.bottom).to.be.closeTo(16, 0.5);
            expect(fourth.left).to.be.closeTo(second.left, 0.5);
            expect(fourth.top - second.bottom).to.be.closeTo(16, 0.5);
        });
        cy.get('.masonry-layout').should(($layout) => {
            expect($layout[0].getBoundingClientRect().height).to.be.closeTo(376, 0.5);
        });
    });

    it('reflows for container width and the configured minimum column width', () => {
        mountLayout();
        cy.get<ComponentWrapper<typeof LayoutFixture>>('@vue').then((wrapper) => wrapper.setProps({ width: 260 }));
        cy.get('[data-item]').should(($items) => {
            const rects = $items.toArray().map((element) => element.getBoundingClientRect());
            for (const [index, rect] of rects.entries()) {
                expect(rect.width).to.be.closeTo(260, 0.5);
                expect(rect.left).to.be.closeTo(rects[0].left, 0.5);
                if (index > 0) expect(rect.top - rects[index - 1].bottom).to.be.closeTo(16, 0.5);
            }
        });
        cy.get<ComponentWrapper<typeof LayoutFixture>>('@vue').then((wrapper) => wrapper.setProps({ width: 960 }));
        cy.get('[data-item]').should(($items) => {
            const [first, second, third, fourth] = $items.toArray().map((element) => element.getBoundingClientRect());
            expect(first.width).to.be.closeTo((960 - 32) / 3, 0.5);
            expect(second.top).to.be.closeTo(first.top, 0.5);
            expect(third.top).to.be.closeTo(first.top, 0.5);
            expect(fourth.left).to.be.closeTo(second.left, 0.5);
            expect(fourth.top - second.bottom).to.be.closeTo(16, 0.5);
        });
        cy.get<ComponentWrapper<typeof LayoutFixture>>('@vue').then((wrapper) => wrapper.setProps({ minimumColumnWidth: 400 }));
        cy.get('[data-item]').should(($items) => {
            const [first, second, third] = $items.toArray().map((element) => element.getBoundingClientRect());
            expect(first.width).to.be.closeTo((960 - 16) / 2, 0.5);
            expect(second.top).to.be.closeTo(first.top, 0.5);
            expect(third.top - second.bottom).to.be.closeTo(16, 0.5);
        });
    });

    it('releases the grid instance when the component unmounts', () => {
        cy.spy(MasonryGrid.prototype, 'destroy').as('destroy');
        mountLayout();
        cy.get<ComponentWrapper<typeof LayoutFixture>>('@vue').then((wrapper) => {
            wrapper.unmount();
        });
        cy.get('@destroy').should('have.been.calledOnce');
    });
});
