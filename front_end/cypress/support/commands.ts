/* eslint-disable @typescript-eslint/method-signature-style */
/// <reference types="cypress" />

import 'cypress-table';
import 'cypress-intercept-formdata';
import type { StaticResponse } from 'cypress/types/net-stubbing';

import { getDatabase, USER_INFO_STORE_NAME } from '../../src/services/database';
import type { LocalSettings } from '../../src/store';

declare global {
    interface Fixture<T> {
        data: T;
    }

    // eslint-disable-next-line @typescript-eslint/no-namespace
    namespace Cypress {
        interface LocalStorageTypes {
            local: LocalSettings;
        }

        interface Chainable {
            /**
             * cypress-get-table 插件，用于获取表格数据
             */
            getTable(): Chainable<Record<string, string>[]>;

            /**
             * 关闭所有通知
             */
            closeElNotifications(): void;

            /**
             * 等待选择器匹配的元素不存在或全部不可见，支持关闭动画和保留 DOM 的浮层。
             * 每次重试重新查询当前文档，使用 Cypress 的可见性判断；返回文档，不返回目标元素。
             * @example cy.shouldBeAbsentOrHidden('.el-dialog', { timeout: 10000 });
             */
            shouldBeAbsentOrHidden(selector: string, options?: Partial<Loggable & Timeoutable>): Chainable<Document>;

            /**
             * 获取本地存储的值
             * @param key - 本地存储的键
             * @example cy.getLocalStorage('authToken')
             */
            getLocalStorage<K extends keyof LocalStorageTypes>(key: K): Chainable<LocalStorageTypes[K] | null>;
            getLocalStorage<T = unknown>(key: string): Chainable<T | null>;

            /**
             * 设置本地存储的值
             * @param key - 本地存储的键
             * @param value - 要存储的值
             * @example cy.setLocalStorage('authToken', 'abc123')
             */
            setLocalStorage(key: string, value: string): void;

            /**
             * 模拟验证码刷新
             * @param options - 请求选项
             * @example cy.mockCaptchaRefresh({})
             */
            mockCaptchaRefresh(options?: Partial<StaticResponse>): void;

            /**
             * 模拟获取邮件验证码
             * @param options - 请求选项
             * @example cy.mockGetEmailCode({})
             */
            mockGetEmailCode(options?: Partial<StaticResponse>): void;

            /**
             * 模拟登录
             * @example cy.mockLogin()
             */
            mockLogin(): void;

            /**
             * 模拟注册
             * @example cy.mockRegister()
             */
            mockRegister(): void;

            /**
             * 让 PlayerName 始终显示 fallback 名称，避免表格测试触发用户信息批量缓存。
             * 勋章状态接口固定返回空列表，避免名字悬停打到未模拟请求。
             */
            mockPlayerNameFallback(): void;

            /** 每次断言重试重新读取表格，支持异步渲染及整表替换。 */
            extractTableData(): Chainable<string[][]>;
            shouldHaveState(expectedStates: (boolean | null)[]): Chainable<JQuery<HTMLInputElement>>;
        }
    }
}

Cypress.Commands.add('getLocalStorage', (key: string) => {
    return cy.window().then((win) => {
        const value = win.localStorage.getItem(key);
        try {
            return value === null ? null : JSON.parse(value) as unknown;
        } catch {
            // If not valid JSON, return the raw string
            return value;
        }
    });
});

Cypress.Commands.add('setLocalStorage', (key: string, value: string) => {
    cy.window().then((win) => {
        win.localStorage.setItem(key, value);
    });
});

Cypress.Commands.add('mockCaptchaRefresh', (options) => {
    let captchaRefreshCount = 0;
    cy.intercept('GET', '/userprofile/refresh_captcha/', (req) => {
        captchaRefreshCount += 1;
        req.reply({
            statusCode: 200,
            headers: { 'Content-Type': 'application/json' },
            body: {
                status: 100,
                hashkey: `testkey${captchaRefreshCount}`,
            },
            ...options,
        });
    }).as('captchaRefresh');
    cy.intercept('GET', '/userprofile/captcha/image/**', {
        fixture: 'test.png',
    }).as('testImage');
});

Cypress.Commands.add('mockGetEmailCode', (options) => {
    cy.intercept('POST', '/userprofile/get_email_captcha/', {
        statusCode: 200,
        headers: { 'Content-Type': 'application/json' },
        body: {
            type: 'success',
            hashkey: 'testkey',
        },
        ...options,
    }).as('getEmailCode');
});

Cypress.Commands.add('mockRegister', () => {
    cy.intercept('POST', '/userprofile/register', (req) => {
        // eslint-disable-next-line @typescript-eslint/no-unsafe-argument -- Cypress 将拦截请求体类型标为 any；这里测试环境固定为 form-urlencoded 字符串。
        const params = new URLSearchParams(req.body);
        const email_captcha = params.get('email_captcha');

        if (email_captcha !== '123456') {
            req.reply({
                type: 'error',
                object: 'emailCode',
            });
            return;
        }
        req.reply({
            type: 'success',
            user: {},
        });
    });
});

Cypress.Commands.add('mockPlayerNameFallback', () => {
    cy.intercept('GET', '**/api/userprofile/avatar/**', { statusCode: 404 }).as('playerNameFallbackAvatar');
    cy.intercept('GET', '**/api/userprofile/infobulk*', { body: [] }).as('playerNameFallbackUserInfoBulk');
    cy.intercept('GET', '**/api/medal/players/state*', { body: [] }).as('playerNameFallbackMedalState');
    cy.then(async () => {
        // Cached names bypass the mocked API and can leak across specs or repeated runs.
        const db = await getDatabase();
        await db.clear(USER_INFO_STORE_NAME);
    });
});

Cypress.Commands.add('mockLogin', () => {
    cy.intercept('POST', '/userprofile/login/', (req) => {
        // eslint-disable-next-line @typescript-eslint/no-unsafe-argument -- Cypress 将拦截请求体类型标为 any；这里测试环境固定为 form-urlencoded 字符串。
        const params = new URLSearchParams(req.body);
        const username = params.get('username');
        const password = params.get('password');
        const captcha = params.get('captcha');
        if (captcha !== 'test') {
            req.reply({
                type: 'error',
                object: 'login',
                category: 'captcha',
            });
            return;
        }
        if (username === 'test' && password === 'test') {
            req.reply({
                type: 'success',
                user: {},
            });
        } else {
            req.reply({
                type: 'error',
                object: 'login',
                category: 'password',
            });
        }
    });
});

Cypress.Commands.add('closeElNotifications', () => {
    cy.document().then((doc) => {
        // Close the stack together before its remaining buttons move during transitions.
        doc.querySelectorAll<HTMLElement>('.el-notification__closeBtn').forEach((button) => {
            button.click();
        });
    });
    cy.shouldBeAbsentOrHidden('.el-notification');
});

Cypress.Commands.add('shouldBeAbsentOrHidden', (selector, options) => {
    return cy.document(options).should((doc) => {
        const $visible = Cypress.$(selector, doc).filter((_, element) => Cypress.dom.isVisible(element));
        expect($visible, `${selector} should be absent or all hidden`).to.have.length(0);
    });
});

Cypress.Commands.addQuery('extractTableData', () => (subject: JQuery) => {
    Cypress.ensure.isElement(subject, 'extractTableData', cy);
    const $table = Cypress.$(subject);
    const $rows = $table.find('> thead > tr, > tbody > tr, > tr');
    const tableData = [] as string[][];
    $rows.each((i, row) => {
        const $row = Cypress.$(row);
        const $cells = $row.find('> th, > td');
        const rowData = [] as string[];
        $cells.each((j, cell) => {
            rowData.push(Cypress.$(cell).text().trim());
        });
        tableData.push(rowData);
    });
    return tableData;
});

Cypress.Commands.add(
    'shouldHaveState',
    { prevSubject: true },
    (subject: JQuery<HTMLInputElement>, expectedStates: (boolean | null)[]) => cy.wrap(subject).should(($inputs) => {
        expect($inputs).to.have.length(expectedStates.length);
        $inputs.each((index, input) => {
            expect(input.type, `checkbox ${index}`).to.equal('checkbox');
            expect(input.indeterminate, `checkbox ${index} indeterminate`).to.equal(expectedStates[index] === null);
            expect(input.checked, `checkbox ${index} checked`).to.equal(expectedStates[index] === true);
        });
    }),
);
