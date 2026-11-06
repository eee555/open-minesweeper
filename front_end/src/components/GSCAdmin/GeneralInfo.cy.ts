import GeneralInfo from './GeneralInfo.vue';

import $axios from '@/http';

interface GeneralInfoProps {
    id: number;
}

function mountOptions(props: GeneralInfoProps) {
    return {
        props,
        global: {
            config: {
                globalProperties: {
                    $axios,
                },
            },
        },
    };
}

function mountGeneralInfo(id: number) {
    cy.mount(GeneralInfo, mountOptions({ id }));
}

function adminInfoBody(data: {
    id?: number;
    order?: number;
    start_time?: string | null;
    end_time?: string | null;
    token?: string | null;
}) {
    return {
        id: data.id ?? 101,
        order: data.order ?? 1,
        start_time: data.start_time ?? null,
        end_time: data.end_time ?? null,
        state: 'n',
        token: data.token ?? null,
    };
}

function bodyParam(body: unknown, key: string): string | null {
    if (typeof body === 'string') {
        return new URLSearchParams(body).get(key);
    }
    if (body instanceof URLSearchParams) {
        return body.get(key);
    }
    if (typeof body === 'object' && body !== null && key in body) {
        const value = (body as Record<string, unknown>)[key];
        if (value === null || value === undefined) return null;
        if (value instanceof Date) return value.toISOString();
        if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
            return String(value);
        }
    }
    return null;
}

function mockEmptyTaskInfo() {
    cy.intercept({ method: 'GET', pathname: '/api/tournament/gsc/task' }, {
        body: null,
    }).as('getGSCTask');
}

describe('<GeneralInfo />', () => {
    it('asks for a non-zero GSC order without loading data', () => {
        let adminInfoRequests = 0;
        cy.intercept({ method: 'GET', pathname: '/api/tournament/gsc/admin-info' }, (req) => {
            adminInfoRequests += 1;
            req.reply({ body: adminInfoBody({}) });
        }).as('getGSCInfo');

        mountGeneralInfo(0);

        cy.contains('请输入非零届数').should('be.visible');
        cy.then(() => {
            expect(adminInfoRequests).to.equal(0);
        });
    });

    it('loads and renders existing GSC admin info', () => {
        mockEmptyTaskInfo();
        cy.intercept({ method: 'GET', pathname: '/api/tournament/gsc/admin-info' }, {
            body: adminInfoBody({
                id: 456,
                order: 7,
                start_time: '2026-07-30T00:00:00Z',
                end_time: '2026-08-03T12:30:45Z',
                token: 'G12345',
            }),
        }).as('getGSCInfo');

        mountGeneralInfo(7);

        cy.wait('@getGSCInfo').its('request.query').should('deep.equal', { order: '7' });
        cy.wait('@getGSCTask').its('request.query').should('deep.equal', { order: '7' });
        cy.contains('开始时间：2026-07-30 08:00:00').should('be.visible');
        cy.contains('结束时间：2026-08-03 20:30:45').should('be.visible');
        cy.contains('标识：G12345').should('be.visible');
        cy.contains('结算后台任务').should('be.visible');
        cy.contains('NULL').should('be.visible');
    });

    it('creates a missing GSC tournament and reloads the admin info', () => {
        let adminInfoRequests = 0;
        mockEmptyTaskInfo();
        cy.intercept({ method: 'GET', pathname: '/api/tournament/gsc/admin-info' }, (req) => {
            adminInfoRequests += 1;
            if (adminInfoRequests === 1) {
                req.reply({ statusCode: 404, body: { detail: 'Not Found' } });
            } else {
                req.reply({
                    body: adminInfoBody({
                        id: 789,
                        order: 8,
                        start_time: '2026-07-30T00:00:00Z',
                        end_time: '2026-08-03T12:30:45Z',
                        token: 'G67890',
                    }),
                });
            }
        }).as('getGSCInfo');
        cy.intercept({ method: 'POST', pathname: '/api/tournament/gsc/new' }, (req) => {
            expect(bodyParam(req.body, 'id')).to.equal('8');
            req.reply({ statusCode: 200 });
        }).as('createGSC');

        mountGeneralInfo(8);

        cy.wait('@getGSCInfo');
        cy.contains('未找到该届信息').should('be.visible');
        cy.contains('button', '创建比赛').click();
        cy.wait('@createGSC');
        cy.wait('@getGSCInfo');
        cy.wait('@getGSCTask');
        cy.then(() => {
            expect(adminInfoRequests).to.equal(2);
        });
        cy.contains('标识：G67890').should('be.visible');
    });

    it('updates the token after user input', () => {
        mockEmptyTaskInfo();
        cy.intercept({ method: 'GET', pathname: '/api/tournament/gsc/admin-info' }, {
            body: adminInfoBody({
                id: 321,
                order: 9,
                start_time: '2026-07-30T00:00:00Z',
                end_time: '2026-08-03T12:30:45Z',
                token: 'G11111',
            }),
        }).as('getGSCInfo');
        cy.intercept({ method: 'POST', url: '**/api/tournament/set' }, (req) => {
            expect(bodyParam(req.body, 'id')).to.equal('321');
            expect(bodyParam(req.body, 'token')).to.equal('G22222');
            req.reply({ statusCode: 200 });
        }).as('setTournament');

        mountGeneralInfo(9);

        cy.wait('@getGSCInfo');
        cy.wait('@getGSCTask');
        cy.contains('标识：G11111').should('be.visible');
        cy.contains('span', '设置标识：').next().find('input').type('G22222');
        cy.contains('button', '修改！').click();

        cy.wait('@setTournament');
        cy.contains('标识：G22222').should('be.visible');
    });

    it('blocks empty token updates until the explicit switch is enabled', () => {
        let setTournamentRequests = 0;
        mockEmptyTaskInfo();
        cy.intercept({ method: 'GET', pathname: '/api/tournament/gsc/admin-info' }, {
            body: adminInfoBody({
                id: 654,
                order: 10,
                start_time: '2026-07-30T00:00:00Z',
                end_time: '2026-08-03T12:30:45Z',
                token: 'G33333',
            }),
        }).as('getGSCInfo');
        cy.intercept({ method: 'POST', url: '**/api/tournament/set' }, (req) => {
            setTournamentRequests += 1;
            expect(bodyParam(req.body, 'id')).to.equal('654');
            expect(bodyParam(req.body, 'token')).to.equal('');
            req.reply({ statusCode: 200 });
        }).as('setTournament');

        mountGeneralInfo(10);

        cy.wait('@getGSCInfo');
        cy.wait('@getGSCTask');
        cy.contains('标识：G33333').should('be.visible');
        cy.get('[data-cy=allow-empty-token] input').should('not.be.checked');
        cy.contains('button', '修改！').click();
        cy.then(() => {
            expect(setTournamentRequests).to.equal(0);
        });

        cy.get('[data-cy=allow-empty-token]').click();
        cy.get('[data-cy=allow-empty-token] input').should('be.checked');
        cy.then(() => {
            expect(setTournamentRequests).to.equal(0);
        });
        cy.contains('button', '修改！').click();
        cy.wait('@setTournament');
        cy.then(() => {
            expect(setTournamentRequests).to.equal(1);
        });
        cy.contains('标识：未设置').should('be.visible');
        cy.closeElNotifications();
        cy.get('[data-cy=allow-empty-token] input').focus();
        cy.realPress('Space');
        cy.get('[data-cy=allow-empty-token] input').should('not.be.checked');
        cy.contains('button', '修改！').click();
        cy.then(() => {
            expect(setTournamentRequests).to.equal(1);
        });
    });
});
