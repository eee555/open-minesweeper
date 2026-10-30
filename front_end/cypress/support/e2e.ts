/* eslint-disable @typescript-eslint/method-signature-style */
// ***********************************************************
// This example support/e2e.ts is processed and
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
import 'cypress-real-events';

const BACKEND_URL = 'http://127.0.0.1:8000';
const DANGERZONE_URL = `${BACKEND_URL}/dangerzone`;

interface AdminRequestOptions extends Partial<Cypress.RequestOptions> {
    url: string;
}

interface DangerzoneUser {
    id: number;
    username: string;
    email?: string;
    password?: string;
    realname?: string;
}

interface DangerzoneVideo {
    user_id: number;
    identifier: string;
    level: string;
    timems: number;
    bv: number;
    upload_time?: string;
    tournament_identifier?: string[];
    state?: string;
    software?: string;
    mode?: string;
    file_size?: number;
    left?: number;
    right?: number;
    double?: number;
    left_ce?: number;
    right_ce?: number;
    double_ce?: number;
    path?: number;
    pluck?: number;
}

interface DangerzoneVideoResponse {
    id: number;
    ongoing_tournament: boolean;
    tournament_ids: number[];
    upload_time: string;
    tournament_identifier: string[];
}

declare global {
    // eslint-disable-next-line @typescript-eslint/no-namespace
    namespace Cypress {
        interface Chainable {
            /**
             * 删除当前会话登录的用户。
             * @example cy.deleteUser();
             * */
            deleteUser(): void;

            /**
             * 清空数据库，恢复初始状态。
             * @example cy.flushDatabase();
             * */
            flushDatabase(): void;

            /**
             * 调用 dangerzone API。仅在后端 E2E_TEST 模式可用。
             */
            dangerzonePost<T = unknown>(path: string, body?: object): Chainable<Response<T>>;

            /**
             * 用当前管理员会话获取 CSRF token，再发送管理写请求。
             * 缺失或错误 CSRF 的拒绝测试仍使用 cy.request。
             */
            adminRequest<T = unknown>(options: AdminRequestOptions): Chainable<Response<T>>;

            /**
             * 注册测试用户。
             */
            registerUser(user: DangerzoneUser): Chainable<Response<unknown>>;

            /**
             * 一次请求注册多个测试用户，返回按输入顺序排列的用户 ID。
             */
            registerUsers(users: DangerzoneUser[]): Chainable<Response<number[]>>;

            /**
             * 创建测试录像。
             */
            createVideo(video: DangerzoneVideo): Chainable<Response<DangerzoneVideoResponse>>;

            /**
             * 创建测试标识。
             */
            createIdentifier(identifier: string, safe?: boolean): Chainable<Response<unknown>>;

            /**
             * 将测试标识绑定到指定用户，可选断言受影响录像数。
             */
            bindIdentifier(userId: number, identifier: string, expectedChangedCount?: number): Chainable<Response<{ changed_count: number }>>;

            /**
             * 将指定用户设为管理员。
             * @param {number} user_id - 用户ID
             * @example cy.setStaff(1);
             */
            setStaff(user_id: number): void;

            /**
             * 通过后端请求创建/恢复登录会话，需要后端开启 E2E_TEST。
             * 登录后由调用方访问目标页面。
             * @param {string} username
             * @param {string} password
             * @example cy.login('user', 'password');
             * cy.visitUser(1);
             * */
            login(username: string, password: string): void;

            /**
             * 访问指定用户的个人主页
             * @param {number} userId - 用户ID
             * @param {string} [tab] - 可选参数，指定要访问的标签页，如'top'、'pb'、'record'、'accountlink'、'videos'、'upload'
             * @example cy.visitUser(1);
             * */
            visitUser(userId: number, tab?: string): void;
        }
    }
}

Cypress.on('uncaught:exception', (err) => {
    console.error('Unhandled exception:', err.message);
    return false; // prevents the test from failing
});

Cypress.on('test:before:run', () => {
    Cypress.automation('remote:debugger:protocol', {
        command: 'Emulation.setTimezoneOverride',
        params: {
            timezoneId: 'Asia/Shanghai', // OR  'UTC'
        },
    });
});

beforeEach(() => {
    cy.intercept('GET', /^https?:\/\/(avatars\.githubusercontent\.com|minesweeper\.online|i2\.hdslb\.com)\/.*/, {
        fixture: 'test.png',
    });
});

Cypress.Commands.add('dangerzonePost', <T = unknown>(path: string, body: object = {}) => {
    return cy.request<T>({
        method: 'POST',
        url: `${DANGERZONE_URL}/${path}`,
        body,
    });
});

Cypress.Commands.add('adminRequest', <T = unknown>(options: AdminRequestOptions) => {
    const url = new URL(options.url, BACKEND_URL);
    if (url.origin !== BACKEND_URL) throw new Error('adminRequest only accepts the configured backend origin.');
    // Fetch for each call: cy.session may have just restored a different cookie jar.
    return cy.request<{ csrf_token: string }>(`${BACKEND_URL}/api/userprofile/admin/csrf`).then(({ body }) => {
        expect(body.csrf_token, 'administrator CSRF token').to.be.a('string').and.not.be.empty;
        const headers: Record<string, unknown> = { ...options.headers };
        if (!Object.keys(headers).some((name) => name.toLowerCase() === 'x-csrftoken')) headers['X-CSRFToken'] = body.csrf_token;
        return cy.request<T>({ ...options, url: url.href, headers });
    });
});

function registrationData(user: DangerzoneUser) {
    return {
        id: user.id,
        username: user.username,
        email: user.email ?? `${user.username}@example.com`,
        password: user.password ?? 'password',
        realname: user.realname,
    };
}

Cypress.Commands.add('registerUser', (user: DangerzoneUser) => {
    return cy.dangerzonePost('register', registrationData(user));
});

Cypress.Commands.add('registerUsers', (users: DangerzoneUser[]) => {
    return cy.dangerzonePost<number[]>('register_bulk', { users: users.map(registrationData) });
});

Cypress.Commands.add('createVideo', (video: DangerzoneVideo) => {
    return cy.dangerzonePost<DangerzoneVideoResponse>('create_video', {
        state: 'd',
        software: 'e',
        mode: '00',
        file_size: 1024,
        left: 100,
        right: 50,
        double: 25,
        left_ce: 100,
        right_ce: 50,
        double_ce: 25,
        path: 1000,
        ...video,
    });
});

Cypress.Commands.add('createIdentifier', (identifier: string, safe = true) => {
    return cy.dangerzonePost('create_identifier', {
        identifier,
        safe,
    });
});

Cypress.Commands.add('bindIdentifier', (userId: number, identifier: string, expectedChangedCount?: number) => {
    return cy.dangerzonePost<{ changed_count: number }>('bind_identifier', {
        user_id: userId,
        identifier,
        safe: true,
    }).then((response) => {
        if (expectedChangedCount !== undefined) {
            expect(response.body.changed_count).to.eq(expectedChangedCount);
        }
        return response;
    });
});

Cypress.Commands.add('setStaff', (id: number) => {
    cy.request({
        method: 'POST',
        url: `${DANGERZONE_URL}/setstaff`,
        body: {
            id: id,
        },
    });
});

Cypress.Commands.add('login', (username: string, password: string) => {
    cy.session(['api', username, password], () => {
        cy.request<{ hashkey: string }>(`${BACKEND_URL}/userprofile/refresh_captcha/`).then(({ body }) => {
            // E2E_TEST 模式的验证码固定为 test，但仍需获取真实 hashkey。
            cy.request<{ type: string }>({
                method: 'POST',
                url: `${BACKEND_URL}/userprofile/login/`,
                form: true,
                log: false,
                body: {
                    username,
                    password,
                    captcha: 'test',
                    hashkey: body.hashkey,
                    set_expiry: 7,
                },
            }).its('body.type').should('eq', 'success');
        });
    }, {
        validate() {
            // 数据库重置或会话过期后，Cypress 会重新执行登录请求。
            cy.request<{ username: string }>({
                url: `${BACKEND_URL}/api/userprofile/info/0`,
                failOnStatusCode: false,
            }).then((response) => {
                expect(response.status).to.eq(200);
                expect(response.body.username).to.eq(username);
            });
        },
    });
});

Cypress.Commands.add('deleteUser', () => {
    cy.request('POST', `${DANGERZONE_URL}/delete_user`).then((response) => {
        expect(response.status).to.eq(200);
    });
});

Cypress.Commands.add('flushDatabase', () => {
    cy.request('POST', `${DANGERZONE_URL}/flush_database`).then((response) => {
        expect(response.status).to.eq(200);
    });
});

Cypress.Commands.add('visitUser', (userId: number, tab?: string) => {
    if (tab !== undefined) {
        cy.visit(`/#/player/${userId}/${tab}`);
    } else {
        cy.visit(`/#/player/${userId}`);
    }
});
