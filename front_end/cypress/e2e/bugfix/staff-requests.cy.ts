export {};

const STAFF = { id: 1, username: 'staff', password: 'staffPassword' };
const USER = { id: 42, username: 'staff-edit-target' };

interface AdminProfile {
    id: number;
    userms_id: number;
    signature: string;
    is_banned: boolean;
    left_avatar_n: number;
    userms_video_num_limit: number;
}

interface TaskDetail {
    id: string;
    status: string;
    task_path: string;
    args_kwargs: { args: unknown[]; kwargs: Record<string, unknown> };
    run_after: string;
}

describe('Staff requests against the backend', () => {
    it('Before All', () => {
        cy.flushDatabase();
        cy.registerUsers([STAFF, USER]);
        cy.setStaff(STAFF.id);
    });

    it('persists staff edits and shows the updated profile on the lightweight PB tab', () => {
        // Observe real responses; request encoding is validated by the backend.
        cy.login(STAFF.username, STAFF.password);
        cy.intercept('GET', `**/api/userprofile/admin/detail/${USER.id}`).as('loadUser');
        cy.intercept('PATCH', `**/api/userprofile/admin/update/${USER.id}`).as('updateProfile');
        // The endpoint allows 5s of caching; immediate post-edit reads must revalidate requests too.
        cy.intercept({ method: 'GET', pathname: `/api/userprofile/info/${USER.id}` }, (request) => {
            request.headers['cache-control'] = 'no-cache';
            request.on('before:response', (response) => {
                response.headers['cache-control'] = 'no-store';
            });
        }).as('publicProfile');
        cy.intercept('GET', `**/api/speedranking/pb/player/${USER.id}`).as('pbRecords');
        cy.intercept('GET', '**/api/userprofile/videolist*').as('allVideos');
        cy.visit('/#/staff/userprofile');
        cy.get('.el-input-number input').clear();
        cy.get('.el-input-number input').type(String(USER.id));
        cy.contains('button', '查询').click();
        cy.wait<unknown, AdminProfile>('@loadUser').then(({ response }) => {
            expect(response?.statusCode).to.eq(200);
            const usermsId = response?.body.userms_id;
            expect(usermsId).to.be.a('number').and.not.eq(USER.id);
            cy.intercept('PATCH', `**/api/msuser/admin/update/${usermsId}`).as('updateUserMS');
        });

        const payload = { signature: '中文 & + =', is_banned: true, left_avatar_n: 0 };
        cy.get('textarea').eq(0).clear();
        cy.get('textarea').eq(0).type(JSON.stringify(payload), { parseSpecialCharSequences: false });
        cy.contains('button', 'PATCH UserProfile（修改用户资料）').click();
        cy.wait('@updateProfile').its('response.statusCode').should('eq', 200);
        cy.get('textarea').eq(0).should('have.value', '{}');

        cy.contains('button', '查询').click();
        cy.wait('@loadUser').its('response.body').should('include', payload);

        cy.closeElNotifications();
        cy.visitUser(USER.id, 'pb');
        cy.url().should('include', `/player/${USER.id}/pb`);
        cy.wait('@publicProfile').its('response.body').should('include', payload);
        cy.wait('@pbRecords').its('response.statusCode').should('eq', 200);
        cy.get('[data-cy=pb-summary]').should('have.attr', 'aria-busy', 'false');
        cy.get('[data-cy=pb-grid-e]').should('be.visible');
        cy.get('.profile-section .signature').should(($signature) => {
            expect($signature.text().trim()).to.eq(payload.signature);
        });
        cy.get('@allVideos.all').should('have.length', 0);

        cy.visit('/#/staff/userprofile');
        cy.get('.el-input-number input').clear();
        cy.get('.el-input-number input').type(String(USER.id));
        cy.contains('button', '查询').click();
        cy.wait('@loadUser').its('response.body').should('include', payload);

        const clearPayload = { signature: '', is_banned: false };
        cy.get('textarea').eq(0).clear();
        cy.get('textarea').eq(0).type(JSON.stringify(clearPayload), { parseSpecialCharSequences: false });
        cy.contains('button', 'PATCH UserProfile（修改用户资料）').click();
        cy.wait('@updateProfile').its('response.statusCode').should('eq', 200);
        cy.get('textarea').eq(0).should('have.value', '{}');
        cy.contains('button', '查询').click();
        cy.wait('@loadUser').its('response.body').should('include', { ...clearPayload, left_avatar_n: 0 });

        cy.get('textarea').eq(1).clear();
        cy.get('textarea').eq(1).type(JSON.stringify({ video_num_limit: 0 }), { parseSpecialCharSequences: false });
        cy.contains('button', 'PATCH UserMS（修改扫雷数据）').click();
        cy.wait('@updateUserMS').its('response.statusCode').should('eq', 200);
        cy.wait('@loadUser').its('response.body.userms_video_num_limit').should('eq', 0);
        cy.get('textarea').eq(1).should('have.value', '{}');
        // The save creates its notification after reloading the profile.
        cy.contains('button', 'PATCH UserMS（修改扫雷数据）').should('not.be.disabled');

        cy.closeElNotifications();
        cy.visitUser(USER.id, 'pb');
        cy.wait('@publicProfile').its('response.body').should('include', clearPayload);
        cy.wait('@pbRecords').its('response.statusCode').should('eq', 200);
        cy.get('[data-cy=pb-grid-e]').should('be.visible');
        cy.get('.profile-section .profile').should('contain.text', USER.username);
        cy.get('.profile-section .signature').should(($signature) => {
            expect($signature.text().trim()).to.eq('');
        });
        cy.get('@allVideos.all').should('have.length', 0);
    });

    it('restarts a failed task and deletes it through the staff page', () => {
        cy.login(STAFF.username, STAFF.password);
        cy.dangerzonePost<TaskDetail>('create_failed_task').then(({ body: failedTask }) => {
            cy.intercept('GET', '**/api/common/tasks/detail').as('loadTasks');
            cy.intercept('POST', '**/api/common/tasks/restart').as('restartTask');
            cy.intercept('POST', '**/api/common/tasks/delete').as('deleteTask');
            cy.visit('/#/staff/task');
            cy.contains('button', '加载任务').click();
            cy.wait('@loadTasks').its('response.statusCode').should('eq', 200);
            cy.contains('tr', failedTask.id).contains('button', '重启').click();
            cy.wait<unknown, TaskDetail>('@restartTask').then(({ response }) => {
                expect(response?.statusCode).to.eq(200);
                const restartedTask = response?.body;
                if (!restartedTask) throw new Error('Missing task restart response');
                expect(restartedTask.id).not.to.eq(failedTask.id);
                expect(restartedTask.status).to.eq('READY');
                expect(restartedTask.task_path).to.eq(failedTask.task_path);
                expect(restartedTask.args_kwargs).to.deep.eq(failedTask.args_kwargs);
                expect(restartedTask.run_after).to.eq(failedTask.run_after);
                // Clicking the rightmost action can scroll the ID column out of view.
                cy.contains('td', restartedTask.id).should('exist');

                cy.contains('button', '加载任务').click();
                cy.wait<unknown, TaskDetail[]>('@loadTasks').then(({ response: loaded }) => {
                    expect(loaded?.statusCode).to.eq(200);
                    expect(loaded?.body).to.deep.include(restartedTask);
                    expect(loaded?.body).to.deep.include(failedTask);
                });

                cy.contains('tr', failedTask.id).find('input[type="checkbox"]').check();
                cy.contains('button', '删除选中任务').click();
                cy.wait('@deleteTask').its('response.statusCode').should('eq', 200);
                cy.contains('td', failedTask.id).should('not.exist');
                cy.contains('button', '加载任务').click();
                cy.wait<unknown, TaskDetail[]>('@loadTasks').then(({ response: loaded }) => {
                    expect(loaded?.statusCode).to.eq(200);
                    expect(loaded?.body.map((task) => task.id)).not.to.include(failedTask.id);
                    expect(loaded?.body).to.deep.include(restartedTask);
                });
                cy.contains('td', failedTask.id).should('not.exist');
                cy.contains('td', restartedTask.id).should('exist');
            });
        });
    });

    it('rebuilds one ranking record through the staff page', () => {
        cy.login(STAFF.username, STAFF.password);
        cy.intercept('POST', '**/api/speedranking/admin/rebuild_record').as('rebuildRecord');
        cy.visit('/#/staff/userprofile');
        cy.contains('[role="tab"]', '排行纪录重建').click();
        cy.contains('button', '重建纪录').should('be.disabled');
        cy.get('.ranking-repair .el-select').eq(0).click();
        cy.contains('.el-select-dropdown__item:visible', '扫雷网规则（NF）').click();
        cy.get('.ranking-repair .el-select').eq(1).click();
        cy.contains('.el-select-dropdown__item:visible', 'Time 总和').click();
        cy.get('.ranking-repair .el-input-number input').type(String(USER.id));
        cy.contains('button', '重建纪录').click();
        cy.wait('@rebuildRecord').then(({ request, response }) => {
            expect(request.headers['content-type']).to.include('application/x-www-form-urlencoded');
            const body = new URLSearchParams(String(request.body));
            expect(body.get('player_id')).to.eq(String(USER.id));
            expect(body.get('ranking_name')).to.eq('saolei_nf');
            expect(body.get('stat')).to.eq('sumt');
            expect(response?.statusCode).to.eq(200);
            expect(response?.body).to.include({ player_id: USER.id, sumt: 2999997, bt: null, it: null, et: null });
        });
        cy.get('output').should('contain.text', '重建完成').and('contain.text', '2999.997');
        cy.closeElNotifications();
    });
});
