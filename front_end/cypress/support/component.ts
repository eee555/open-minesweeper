// ***********************************************************
// This example support/component.ts is processed and
// loaded automatically before your test files.
//
// This is a great place to put global configuration and
// behavior that modifies Cypress.
//
// You can change the location of this file or turn off
// automatically serving support files with the
// 'supportFile' configuration option.
//
// You can read more here:
// https://on.cypress.io/configuration
// ***********************************************************

// Import commands.js using ES2015 syntax:
import './commands';
import '../../src/setup';

import type { VueWrapper } from '@vue/test-utils';
import { mount } from 'cypress/vue';
import 'cypress-real-events';

// Augment the Cypress namespace to include type definitions for
// your custom command.
// Alternatively, can be defined in cypress/support/component.d.ts
// with a <reference path="./component" /> at the top of your spec.
declare global {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Vue SFC constructor helpers must accept arbitrary constructor args and instance shapes.
    type ComponentWrapper<C extends abstract new (...args: any) => any> = VueWrapper<InstanceType<C>>;

    // eslint-disable-next-line @typescript-eslint/no-namespace
    namespace Cypress {
        interface Chainable {
            mount: typeof mount;
        }
    }
}

Cypress.Commands.add('mount', (...args) => {
    return mount(...args).then((result) => {
        cy.wrap(result.wrapper).as('vue');
        return cy.wrap(result);
    });
});

Cypress.on('uncaught:exception', (err) => !err.message.includes('ResizeObserver loop'));

Cypress.on('test:before:run', () => {
    Cypress.automation('remote:debugger:protocol', {
        command: 'Emulation.setTimezoneOverride',
        params: {
            timezoneId: 'Asia/Shanghai', // OR  'UTC'
        },
    });
});

// Example use:
// cy.mount(MyComponent)
