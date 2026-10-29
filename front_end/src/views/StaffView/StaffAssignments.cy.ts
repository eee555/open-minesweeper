import StaffAssignments from './StaffAssignments.vue';

const endpoint = '**/api/userprofile/admin/staff';

function mountPage() {
    cy.mount(StaffAssignments);
    cy.wait('@access');
}

describe('<StaffAssignments />', () => {
    it('hides permission controls when the backend denies superuser access', () => {
        cy.intercept('GET', endpoint, { statusCode: 401, body: { detail: 'Unauthorized' } }).as('access');
        mountPage();
        cy.get('[data-cy=staff-assignment-access-error]').should('contain.text', '普通管理员无权访问');
        cy.get('[data-cy=staff-assignment-controls]').should('not.exist');
    });

    it('grants and revokes staff permissions using JSON and the initialized CSRF token', () => {
        cy.intercept('GET', endpoint, { body: { csrf_token: 'token' } }).as('access');
        cy.intercept('POST', endpoint, (request) => {
            expect(request.headers['content-type']).to.contain('application/json');
            expect(request.headers['x-csrftoken']).to.equal('token');
            const body = request.body as { user_id: number; is_staff: boolean };
            request.reply({ body: { id: body.user_id, is_staff: body.is_staff } });
        }).as('assign');
        mountPage();
        cy.get('[data-cy=staff-assignment-grant]').should('be.disabled');
        cy.get('[data-cy=staff-assignment-user-id]').type('0');
        cy.get('[data-cy=staff-assignment-revoke]').should('be.disabled');
        cy.get('[data-cy=staff-assignment-user-id]').clear().type('42');
        cy.get('[data-cy=staff-assignment-grant]').click();
        cy.wait('@assign').its('request.body').should('deep.equal', { user_id: 42, is_staff: true });
        cy.get('[data-cy=staff-assignment-result]').should('contain.text', '用户 #42：已设为管理员');
        cy.get('[data-cy=staff-assignment-revoke]').click();
        cy.wait('@assign').its('request.body').should('deep.equal', { user_id: 42, is_staff: false });
        cy.get('[data-cy=staff-assignment-result]').should('contain.text', '已取消管理员权限');
    });

    it('reports rejected assignments without displaying a successful result', () => {
        cy.intercept('GET', endpoint, { body: { csrf_token: 'token' } }).as('access');
        cy.intercept('POST', endpoint, { statusCode: 409, body: { detail: 'Memorial accounts cannot have administrative permissions.' } }).as('assign');
        mountPage();
        cy.get('[data-cy=staff-assignment-user-id]').type('42');
        cy.get('[data-cy=staff-assignment-grant]').click();
        cy.wait('@assign');
        cy.get('[data-cy=staff-assignment-error]').should('contain.text', '纪念账号不能拥有管理员权限');
        cy.get('[data-cy=staff-assignment-result]').should('not.exist');
        cy.get('[data-cy=staff-assignment-grant]').should('not.be.disabled');
    });
});
