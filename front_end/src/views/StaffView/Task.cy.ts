import PrimeVue from 'primevue/config';

import Task from './Task.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { DjangoTaskResultStatus } from '@/utils/common/structInterface';

function task(id: string, status: DjangoTaskResultStatus) {
    return {
        id,
        status,
        enqueued_at: '2026-11-05T08:00:00+08:00',
        run_after: '2026-11-05T08:00:00+08:00',
        started_at: null,
        finished_at: null,
        args_kwargs: { args: [], kwargs: {} },
        priority: 0,
        task_path: 'example.task',
        worker_ids: [],
        queue_name: 'default',
        backend_name: 'default',
        return_value: null,
        exception_class_path: '',
        traceback: '',
    };
}

function expectTaskIds(ids: string[]) {
    cy.get('.p-datatable-tbody').extractTableData().should((rows: string[][]) => {
        expect(rows.map((row) => row[1])).to.deep.equal(ids);
    });
}

describe('staff task status selection', () => {
    it('filters immediately using the updated value and distinguishes NULL from clearing the filter', () => {
        cy.intercept('GET', '/api/common/tasks/summary', { total: 3, status: { READY: 1, RUNNING: 0, FAILED: 1, SUCCESSFUL: 0, NULL: 1 } });
        cy.intercept('GET', '/api/common/tasks/detail', [task('task-ready', 'READY'), task('task-null', 'NULL'), task('task-failed', 'FAILED')]).as('tasks');
        cy.mount(Task, { global: { plugins: [i18n, PrimeVue], config: { globalProperties: { $axios } } } });
        cy.contains('button', 'Load tasks').click();
        cy.wait('@tasks');
        expectTaskIds(['task-ready', 'task-null', 'task-failed']);

        cy.get('.p-datatable-column-filter-button').click();
        cy.get('select[aria-label="Status"]').should('have.prop', 'selectedIndex', 0);
        cy.get('select[aria-label="Status"]').select('NULL');
        expectTaskIds(['task-null']);
        cy.get('select[aria-label="Status"]').select('READY');
        expectTaskIds(['task-ready']);
        cy.get('select[aria-label="Status"]').select('All');
        expectTaskIds(['task-ready', 'task-null', 'task-failed']);

        cy.get('select[aria-label="Status"]').select('FAILED');
        expectTaskIds(['task-failed']);
        cy.get('.p-datatable-filter-clear-button').click();
        expectTaskIds(['task-ready', 'task-null', 'task-failed']);
        cy.shouldBeAbsentOrHidden('.p-datatable-filter-overlay');
        cy.get('.p-datatable-column-filter-button').click();
        cy.get('select[aria-label="Status"]').should('have.prop', 'selectedIndex', 0);
    });
});
