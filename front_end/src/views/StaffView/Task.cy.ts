import Task from './Task.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { DjangoTaskResultStatus } from '@/utils/common/structInterface';

function task(id: string, status: DjangoTaskResultStatus = 'READY', taskPath = 'example.task') {
    return {
        id,
        status,
        enqueued_at: '2026-11-05T08:00:00+08:00',
        run_after: '2026-11-05T08:00:00+08:00',
        started_at: null,
        finished_at: null,
        args_kwargs: { args: [], kwargs: {} },
        priority: 0,
        task_path: taskPath,
        worker_ids: [],
        queue_name: 'default',
        backend_name: 'default',
        return_value: null,
        exception_class_path: '',
        traceback: 'example traceback',
    };
}
type TaskRow = ReturnType<typeof task>;
function mountTasks(tasks: TaskRow[]) {
    cy.intercept('GET', '/api/common/tasks/summary', { total: tasks.length, status: { READY: tasks.length, RUNNING: 0, FAILED: 0, SUCCESSFUL: 0, NULL: 0 } }).as('summary');
    cy.intercept('GET', '/api/common/tasks/detail*', (req) => {
        const status = String(req.query.status ?? '');
        const path = String(req.query.task_path ?? '');
        const filtered = tasks.filter((item) => (!status || item.status === status) && item.task_path.includes(path));
        const start = Number(req.query.start);
        const count = Number(req.query.count);
        req.reply({ total: filtered.length, start, count, items: filtered.slice(start - 1, start - 1 + count) });
    }).as('tasks');
    cy.mount(Task, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
    cy.wait('@tasks').its('request.query').should('include', { start: '1', count: '10', sort: 'enqueued_at', reverse: 'true' });
}
function expectTaskIds(ids: string[]) {
    cy.get('[data-cy=task-table] tbody').extractTableData().should((rows: string[][]) => {
        expect(rows.map((row) => row[1])).to.deep.equal(ids);
    });
}
function selectTask(id: string) {
    cy.get(`[data-cy=task-table] input[aria-label="Select task ${id}"]`).check();
}

describe('staff task table', () => {
    it('filters on updated server values, commits paths only on Enter and clears filters', () => {
        mountTasks([task('task-ready'), task('task-null', 'NULL'), task('task-failed', 'FAILED', 'other.task')]);
        expectTaskIds(['task-ready', 'task-null', 'task-failed']);
        cy.get('[data-cy=filter-status]').select('READY');
        cy.wait('@tasks').its('request.query').should('include', { status: 'READY', start: '1' });
        expectTaskIds(['task-ready']);
        cy.get('[data-cy=filter-status]').select('FAILED');
        cy.wait('@tasks');
        expectTaskIds(['task-failed']);
        cy.get('[data-cy=filter-status]').select('');
        cy.wait('@tasks');
        cy.get('[data-cy=filter-path]').type('other');
        cy.get('@tasks.all').should('have.length', 4);
        cy.get('[data-cy=filter-path]').type('{enter}');
        cy.wait('@tasks').its('request.query').should('include', { task_path: 'other', start: '1' });
        expectTaskIds(['task-failed']);
        cy.get('[data-cy=clear-filters]').click();
        cy.wait('@tasks').its('request.query').should('include', { status: '', task_path: '', start: '1' });
        expectTaskIds(['task-ready', 'task-null', 'task-failed']);
        cy.get('@tasks.all').should('have.length', 6);
    });

    it('requests arbitrary starting indices, changes capacity and resets on server sort/filter', () => {
        const tasks = Array.from({ length: 27 }, (_, index) => task(`task-${String(index + 1).padStart(2, '0')}`));
        mountTasks(tasks);
        cy.get('[data-cy=task-pagination] [data-cy=jump]').clear().type('13{enter}');
        cy.wait('@tasks').its('request.query').should('include', { start: '13', count: '10' });
        expectTaskIds(tasks.slice(12, 22).map((row) => row.id));
        cy.get('[data-cy=task-pagination] [data-cy=report]').should('have.text', '13-22 / 27');
        cy.get('[data-cy=task-pagination] [data-cy=page-size]').select('25');
        cy.wait('@tasks').its('request.query').should('include', { start: '1', count: '25' });
        cy.get('[data-cy=task-pagination] [data-cy=next]').click();
        cy.wait('@tasks').its('request.query').should('include', { start: '26', count: '25' });
        expectTaskIds(['task-26', 'task-27']);
        cy.get('[data-cy=sort-priority]').click();
        cy.wait('@tasks').its('request.query').should('include', { start: '1', sort: 'priority', reverse: 'false' });
        cy.get('[data-cy=sort-priority]').closest('th').should('have.attr', 'aria-sort', 'ascending');
        cy.get('[data-cy=sort-enqueued_at]').closest('th').should('have.attr', 'aria-sort', 'none');
        cy.get('[data-cy=sort-priority]').click();
        cy.wait('@tasks').its('request.query').should('include', { sort: 'priority', reverse: 'true' });
        cy.get('[data-cy=task-pagination] [data-cy=next]').click();
        cy.wait('@tasks');
        cy.get('[data-cy=filter-status]').select('FAILED');
        cy.wait('@tasks').its('request.query').should('include', { start: '1', status: 'FAILED' });
        cy.get('[data-cy=task-table]').should('contain.text', 'No tasks');
        cy.get('[data-cy=task-pagination] [data-cy=report]').should('have.text', '0-0 / 0');
        cy.get('@tasks.all').should('have.length', 8);
    });

    it('keeps selection across ranges, handles partial deletion and corrects a shrunken range', () => {
        const tasks = Array.from({ length: 11 }, (_, index) => task(`task-${String(index + 1).padStart(2, '0')}`));
        let rejectDeletion = true;
        cy.intercept('POST', '/api/common/tasks/delete', (req) => {
            const { task_id: id } = req.body as { task_id: string };
            if (id === 'task-11' && rejectDeletion) {
                req.reply({ statusCode: 409, body: 'Task is locked.' });
            } else {
                tasks.splice(tasks.findIndex((row) => row.id === id), 1);
                req.reply({ body: null });
            }
        }).as('delete');
        mountTasks(tasks);
        selectTask('task-01');
        cy.get('[data-cy=select-page]').shouldHaveState([null]);
        cy.get('[data-cy=task-pagination] [data-cy=next]').click();
        cy.wait('@tasks');
        cy.get('[data-cy=select-page]').check();
        cy.get('[data-cy=delete-tasks]').click();
        cy.wait('@delete').its('request.body').should('deep.equal', { task_id: 'task-01' });
        cy.wait('@delete').its('response.statusCode').should('eq', 409);
        cy.wait('@tasks').its('request.query').should('include', { start: '11' });
        cy.wait('@tasks').its('request.query').should('include', { start: '10' });
        cy.closeElNotifications();
        expectTaskIds(['task-11']);
        cy.get('[data-cy=select-task]').shouldHaveState([true]);
        cy.get('[data-cy=delete-tasks]').should('not.be.disabled');
        cy.then(() => {
            rejectDeletion = false;
        });
        cy.get('[data-cy=delete-tasks]').click();
        cy.wait('@delete').its('request.body').should('deep.equal', { task_id: 'task-11' });
        cy.wait('@tasks');
        cy.wait('@tasks').its('request.query').should('include', { start: '9' });
        expectTaskIds(['task-10']);
        cy.get('[data-cy=select-task]').shouldHaveState([false]);
        cy.get('[data-cy=delete-tasks]').should('be.disabled');
        cy.get('[data-cy=task-pagination] [data-cy=report]').should('have.text', '9-9 / 9');
    });

    it('preserves restart restrictions, prints traceback and refreshes after cleanup', () => {
        const tasks = [task('task-failed', 'FAILED'), task('task-blocked', 'FAILED', 'accountlink.tasks.task_saolei_profile')];
        cy.intercept('POST', '/api/common/tasks/restart', (req) => {
            tasks.push(task('task-restarted'));
            req.reply({ body: tasks[tasks.length - 1], delay: 150 });
        }).as('restart');
        cy.intercept('POST', '/api/common/tasks/cleanup', (req) => {
            tasks.splice(0, tasks.length);
            req.reply({ body: 2 });
        }).as('cleanup');
        cy.window().then((win) => cy.stub(win.console, 'log').as('traceback'));
        mountTasks(tasks);
        cy.get('[data-cy=restart-task]').last().should('be.disabled');
        cy.get('[data-cy=task-traceback]').first().click();
        cy.get('@traceback').should('have.been.calledWith', 'example traceback');
        cy.get('[data-cy=restart-task]').first().click();
        cy.get('[data-cy=restart-task]').first().should('be.disabled');
        cy.wait('@restart').its('request.body').should('deep.equal', { task_id: 'task-failed' });
        cy.wait('@tasks');
        expectTaskIds(['task-failed', 'task-blocked', 'task-restarted']);
        cy.get('[data-cy=cleanup-tasks]').click();
        cy.wait('@cleanup');
        cy.wait('@tasks');
        cy.get('[data-cy=task-table]').should('contain.text', 'No tasks');
        cy.get('@restart.all').should('have.length', 1);
        cy.get('@cleanup.all').should('have.length', 1);
    });
});
