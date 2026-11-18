function visitWithStartupScript(script: string) {
    cy.intercept('GET', 'http://localhost:8080/', (request) => {
        request.continue((response) => {
            if (typeof response.body !== 'string') return;
            response.body = response.body.replace('<head>', `<head><script>${script}</script>`);
        });
    });
    cy.visit('/');
}

describe('outdated browser', () => {
    it('shows an upgrade message instead of the resource loader when toReversed is missing', () => {
        visitWithStartupScript('Reflect.deleteProperty(Array.prototype, "toReversed");');

        cy.contains('最低要求：Chrome 119+、Firefox 124+、Safari 17.4+、Edge 119+').should('be.visible');
        cy.contains('正在加载资源').should('not.be.visible');
    });

    it('replaces the resource loader when startup throws toReversed is not a function', () => {
        cy.on('uncaught:exception', (error) => !error.message.includes('toReversed'));
        visitWithStartupScript([
            'Object.defineProperty(Array.prototype, "toReversed", {',
            'configurable: true, writable: true,',
            'value: function () { throw new TypeError("toReversed is not a function"); }',
            '});',
        ].join(''));

        cy.contains('最低要求：Chrome 119+、Firefox 124+、Safari 17.4+、Edge 119+').should('be.visible');
        cy.contains('正在加载资源').should('not.be.visible');
    });

    for (const method of ['any', 'timeout']) {
        it(`shows an upgrade message when AbortSignal.${method} is missing`, () => {
            visitWithStartupScript(`Reflect.deleteProperty(AbortSignal, "${method}");`);

            cy.contains('最低要求：Chrome 119+、Firefox 124+、Safari 17.4+、Edge 119+').should('be.visible');
            cy.contains('正在加载资源').should('not.be.visible');
        });
    }

    it('loads the app when the browser provides the required APIs', () => {
        cy.visit('/');
        cy.get('#app[data-v-app]', { timeout: Cypress.config('pageLoadTimeout') }).should('be.visible');
        cy.contains('最低要求：Chrome 119+、Firefox 124+、Safari 17.4+、Edge 119+').should('not.exist');
    });
});
