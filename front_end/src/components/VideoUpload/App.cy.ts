
import { interceptFormData } from 'cypress-intercept-formdata';
import PrimeVue from 'primevue/config';
import type { ComponentProps } from 'vue-component-type-helpers';

import App from './App.vue';

import { binaryStringToUint8Array } from '@/../cypress/support/stupidCypress';
import $axios from '@/http';
import i18n from '@/i18n';
import { local } from '@/store';
import { MS_State } from '@/utils/ms_const';

function tableRowError(status: string) {
    return { '': '', Bv: '', Bvs: '', Status: status, Time: '', Level: '', 'End Time': '', Mode: '' };
}

const fixtures = {
    expAvf: {
        filename: 'Exp_FL_35.09_3BV=132_3BVs=3.76_Pu Tian Yi(Hu Bei).avf',
        tableData: { '': '', Bv: '132', Bvs: '3.762', Status: 'Pass', Time: '35.090', Level: 'Expert', Mode: 'Standard', 'End Time': '2023-10-05 21:25:57' },
        response: {
            type: 'success',
            data: {
                id: 1,
                state: MS_State.Official,
            },
        },
    },
    expMvf: {
        filename: 'Lin_Jin_Fan_Exp_60.623bv207.mvf',
        tableData: { '': '', Bv: '207', Bvs: '3.472', Status: 'Need manual approval', Time: '59.620', Level: 'Expert', Mode: 'Standard', 'End Time': '2011-08-03 06:49:03' },
        response: {
            type: 'error',
            object: 'file',
        },
    },
    cusAvf: {
        filename: '4376-Custom-FL-30x24-860.360-357-226m-20220522.avf',
        tableData: { '': '', Bv: '357', Bvs: '0.415', Status: 'This custom board is currently not supported', Time: '860.360', Level: '24x30/226', Mode: 'Standard', 'End Time': '2022-05-22 23:30:49' },
    },
    cusEvf8_8_40: {
        filename: 'c_10_129.073_24_0.186_Pu Tian Yi(Hu Bei).evf',
        tableData: { '': '', Bv: '24', Bvs: '0.186', Status: 'Pass', Time: '129.073', Level: '8x8/40', Mode: 'Lucky', 'End Time': '2026-06-30 19:25:04' },
    },
    failed: {
        filename: 'c_10_39.832_24_0.477_Pu Tian Yi(Hu Bei)_fail.evf',
        tableData: { '': '', Bv: '20', Bvs: '0.502', Status: 'Game not finished', Time: '39.832', Level: '8x8/40', Mode: 'Lucky', 'End Time': '2026-07-01 00:34:41' },
    },
    intRmv: {
        filename: '3819-Time-1616-NF-9469-32-20151031.rmv',
        tableData: { '': '', Bv: '32', Bvs: '3.379', Status: 'Pass', Time: '9.469', Level: 'Intermediate', Mode: 'Standard', 'End Time': '2015-10-31 22:53:35' },
        response: {
            type: 'success',
            object: 'videomodel',
            category: 'upload',
            data: {
                id: 2,
                state: MS_State.Identifier,
            },
        },
    },
    json: {
        filename: 'example.json',
    },
};

function loadFixture(label: keyof typeof fixtures, alias: string) {
    cy.fixture(fixtures[label].filename, 'binary').then((fileContent) => {
        cy.wrap(binaryStringToUint8Array(fileContent)).as(alias);
    });
}

function mockUploadResponse() {
    cy.intercept('POST', '/common/uploadvideo/', (req) => {
        switch (interceptFormData(req).file) {
            case 'exp.avf':
                req.reply({
                    statusCode: 200,
                    body: fixtures.expAvf.response,
                });
                break;
            case 'int.rmv':
                req.reply({
                    statusCode: 200,
                    body: fixtures.intRmv.response,
                });
                break;
            case 'exp.mvf':
                req.reply({
                    statusCode: 200,
                    body: fixtures.expMvf.response,
                });
                break;
        }
    }).as('uploadRequest');
}

function mountOptions(props: ComponentProps<typeof App>) {
    return {
        props: props,
        global: {
            plugins: [i18n, PrimeVue],
            config: {
                globalProperties: {
                    $axios,
                },
            },
        },
    };
}

describe('VideoUpload Component', () => {
    beforeEach(() => {
    // 默认关闭自动上传和自动删除，以便单独测试上传按钮和表格状态
        local.value.autoUploadAfterParse = false;
        local.value.autoRemoveAfterUpload = false;
    });

    it('shows real name required when user is anonymous', () => {
        cy.mount(App, mountOptions({ isUserAnonymous: true }));
        cy.contains('Real name required').should('be.visible');
        cy.get('input[type="file"]').should('be.disabled');
    });

    it('shows drag area and checkboxes when user is not anonymous', () => {
        cy.mount(App, mountOptions({ isUserAnonymous: false }));
        cy.contains('Drag files here or click here to select').should('be.visible');
        cy.contains('Auto-upload after parsing').should('be.visible');
        cy.contains('Auto-remove after uploading').should('be.visible');
    });

    it('keeps upload options outside the file picker button', () => {
        cy.mount(App, mountOptions({ isUserAnonymous: false }));
        cy.get('input[type=file]').then(($input) => {
            cy.stub($input[0] as HTMLInputElement, 'click').as('pick');
        });
        cy.contains('label', 'Auto-upload after parsing').click();
        cy.contains('label', 'Auto-upload after parsing').find('input').should('be.checked');
        cy.contains('label', 'Auto-remove after uploading').click();
        cy.contains('label', 'Auto-remove after uploading').find('input').should('be.checked');
        cy.contains('label', 'Auto-upload after parsing').find('input').focus();
        cy.realPress('Space');
        cy.contains('label', 'Auto-upload after parsing').find('input').should('not.be.checked');
        cy.window().its('localStorage').invoke('getItem', 'local').should((value: string | null) => {
            const settings = JSON.parse(value ?? '{}') as { autoUploadAfterParse?: boolean; autoRemoveAfterUpload?: boolean };
            expect(settings.autoUploadAfterParse).to.equal(false);
            expect(settings.autoRemoveAfterUpload).to.equal(true);
        });
        cy.get('.base-file-input button input').should('not.exist');
        cy.get('@pick').should('not.have.been.called');
        cy.contains('button', 'Drag files here or click here to select').click();
        cy.get('@pick').should('have.been.calledOnce');
    });

    it('File parsing and table rendering', () => {
        cy.viewport(500, 1000);
        cy.mount(App, mountOptions({
            isUserAnonymous: false,
        }));

        // 准备录像文件
        loadFixture('expAvf', 'videoFileExpAvf');
        loadFixture('expMvf', 'videoFileExpMvf');
        loadFixture('cusAvf', 'videoFileCusAvf');
        loadFixture('cusEvf8_8_40', 'videoFileCusEvf8_8_40');
        loadFixture('intRmv', 'videoFileIntRmv');
        loadFixture('failed', 'videoFileFailed');
        loadFixture('json', 'fileJson');

        cy.get('input[type=file]').selectFile([
            { contents: '@videoFileExpAvf', fileName: 'exp.avf' }, // 高级, pass
            { contents: '@videoFileIntRmv', fileName: 'int.rmv' }, // 中级, pass
            { contents: '@videoFileCusAvf', fileName: 'cus.avf' }, // custom
            { contents: '@videoFileCusEvf8_8_40', fileName: 'cus.evf' }, // custom
            { contents: '@videoFileFailed', fileName: 'failed.evf' }, // 炸局
            { contents: '@fileJson', fileName: 'json.avf' }, // parse
            { contents: '@fileJson', fileName: 'json.json' }, // fileext
            {
                contents: '@videoFileIntRmv',
                fileName: 'a'.repeat(101) + '.avf',
            }, // filename
            {
                contents: '@videoFileExpAvf',
                fileName: 'theSameValidExp.avf',
            }, // 查重
            { contents: '@videoFileExpMvf', fileName: 'exp.mvf' }, // 高级, needApprove
        ], { force: true });

        cy.get('table:visible');
        cy.contains('Parsing files').should('not.exist');
        cy.get('table:visible').getTable().should((tableData) => {
            expect(tableData.length).to.equal(9);
            expect(tableData[0]).to.deep.equal(fixtures.expAvf.tableData);
            expect(tableData[1]).to.deep.equal(fixtures.intRmv.tableData);
            expect(tableData[2]).to.deep.equal(fixtures.cusAvf.tableData);
            expect(tableData[3]).to.deep.equal(fixtures.cusEvf8_8_40.tableData);
            expect(tableData[4]).to.deep.equal(fixtures.failed.tableData);
            expect(tableData[5]).to.deep.equal(tableRowError('Cannot parse the file'));
            expect(tableData[6]).to.deep.equal(tableRowError('Invalid file extension'));
            expect(tableData[7]).to.deep.equal(tableRowError('File name exceeds 100 bytes'));
            expect(tableData[8]).to.deep.equal(fixtures.expMvf.tableData);
        });
    });

    it('Table multi-selection', () => {
        cy.mount(App, mountOptions({ isUserAnonymous: false }));

        // 准备录像文件
        loadFixture('expAvf', 'videoFileExpAvf');
        loadFixture('intRmv', 'videoFileIntRmv');
        loadFixture('cusAvf', 'videoFileCusAvf');

        cy.get('input[type=file]').selectFile([
            { contents: '@videoFileExpAvf', fileName: 'exp.avf' },
            { contents: '@videoFileIntRmv', fileName: 'int.rmv' },
            { contents: '@videoFileCusAvf', fileName: 'cus.avf' },
        ], { force: true });

        cy.get('table:visible');
        cy.contains('Parsing files').should('not.exist');

        // 初始状态全不选
        cy.get('table:visible .checkbox-input').shouldHaveState([false, false, false, false]);

        // 全选
        cy.get('table:visible .checkbox-input').first().parent('label').click();
        cy.get('table:visible .checkbox-input').shouldHaveState([true, true, true, true]);

        // 全不选
        cy.get('table:visible .checkbox-input').first().click();
        cy.get('table:visible .checkbox-input').shouldHaveState([false, false, false, false]);

        // 选择部分
        cy.get('table:visible .checkbox-input').eq(1).parent('label').click();
        cy.get('table:visible .checkbox-input').eq(2).click();
        cy.get('table:visible .checkbox-input').shouldHaveState([null, true, true, false]);

        // 逐步全选
        cy.get('table:visible .checkbox-input').eq(3).click();
        cy.get('table:visible .checkbox-input').shouldHaveState([true, true, true, true]);

        // 部分取消
        cy.get('table:visible .checkbox-input').eq(2).click();
        cy.get('table:visible .checkbox-input').shouldHaveState([null, true, false, true]);

        // 中间状态全不选
        cy.get('table:visible .checkbox-input').first().click();
        cy.get('table:visible .checkbox-input').shouldHaveState([false, false, false, false]);

        // Space 选择一行，再从半选清空
        cy.get('table:visible .checkbox-input').eq(1).focus();
        cy.realPress('Space');
        cy.get('table:visible .checkbox-input').shouldHaveState([null, true, false, false]);
        cy.get('table:visible .checkbox-input').first().focus();
        cy.realPress('Space');
        cy.get('table:visible .checkbox-input').shouldHaveState([false, false, false, false]);
    });

    it('Response status', () => {
        mockUploadResponse();
        cy.mount(App, mountOptions({ isUserAnonymous: false }));

        loadFixture('expAvf', 'videoFileExpAvf');
        loadFixture('intRmv', 'videoFileIntRmv');
        loadFixture('cusAvf', 'videoFileCusAvf');
        loadFixture('expMvf', 'videoFileExpMvf');

        cy.get('input[type=file]').selectFile([
            { contents: '@videoFileExpAvf', fileName: 'exp.avf' },
            { contents: '@videoFileIntRmv', fileName: 'int.rmv' },
            { contents: '@videoFileCusAvf', fileName: 'cus.avf' },
            { contents: '@videoFileExpMvf', fileName: 'exp.mvf' },
        ], { force: true });

        cy.get('table:visible .checkbox-input').first().click(); // 全选
        cy.get('button').contains('Upload').click();

        cy.contains('Uploading: 0 / 4');
        cy.contains('Uploading: 1 / 4');
        cy.contains('Uploading: 3 / 4');
        cy.contains('Uploading').should('not.exist');

        cy.get('table:visible').getTable().should((tableData) => {
            expect(tableData.length).to.equal(4);
            expect(tableData[0]).to.deep.equal({ ...fixtures.expAvf.tableData, Status: 'Success' });
            expect(tableData[1]).to.deep.equal({ ...fixtures.intRmv.tableData, Status: 'New identifier' });
            expect(tableData[2]).to.deep.equal(fixtures.cusAvf.tableData);
            expect(tableData[3]).to.deep.equal({ ...fixtures.expMvf.tableData, Status: 'Video already exists' });
        });
    });

    for (const autoUpload of [false, true]) {
        for (const statusCode of [402, 500]) {
            it(`shows the HTTP ${statusCode} failure status with auto-upload ${autoUpload}`, () => {
                const expectedStatus = statusCode === 402 ? 'Video quota reached' : 'Upload fail';
                local.value.autoUploadAfterParse = autoUpload;
                local.value.autoRemoveAfterUpload = true;
                cy.intercept('POST', '/common/uploadvideo/', { statusCode, body: '' }).as('uploadRequest');
                const onUpload = cy.spy().as('onUpload');
                cy.mount(App, mountOptions({ isUserAnonymous: false, onOnUpload: onUpload }));

                loadFixture('expAvf', 'videoFileExpAvf');
                cy.get('input[type=file]').selectFile([
                    { contents: '@videoFileExpAvf', fileName: 'exp.avf' },
                ], { force: true });

                if (!autoUpload) {
                    cy.contains('Parsing files').should('not.exist');
                    cy.get('table:visible .checkbox-input').first().click();
                    cy.get('button').contains('Upload').click();
                }

                cy.wait('@uploadRequest').its('response.statusCode').should('eq', statusCode);
                // getTable captures a snapshot; wait for Vue to render the final status before reading it.
                cy.contains('table:visible tbody td', expectedStatus).should('be.visible');
                cy.get('input[type=file]').should('not.be.disabled');
                cy.contains('Uploading').should('not.exist');
                cy.get('table:visible').getTable().should('deep.equal', [
                    { ...fixtures.expAvf.tableData, Status: expectedStatus },
                ]);
                cy.get('@onUpload').should('not.have.been.called');
            });
        }
    }

    it('retains a rejected upload for retry while ranking anchors refresh', () => {
        local.value.autoUploadAfterParse = true;
        local.value.autoRemoveAfterUpload = true;
        cy.intercept('POST', '/common/uploadvideo/', { statusCode: 503, headers: { 'Retry-After': '1' }, body: { type: 'error', object: 'top', category: 'refreshing' } }).as('busy');
        cy.mount(App, mountOptions({ isUserAnonymous: false }));
        loadFixture('expAvf', 'videoFileExpAvf');
        cy.get('input[type=file]').selectFile([{ contents: '@videoFileExpAvf', fileName: 'exp.avf' }], { force: true });
        cy.wait('@busy');
        cy.get('.el-notification').should('contain.text', 'Ranking anchors are being refreshed').and('contain.text', 'retry');
        cy.closeElNotifications();
        cy.contains('Uploading').should('not.exist');
        cy.get('table:visible').getTable().should('deep.equal', [fixtures.expAvf.tableData]);
        mockUploadResponse();
        cy.get('table:visible .checkbox-input').first().click();
        cy.get('button').contains('Upload').click();
        cy.wait('@uploadRequest');
        cy.get('table:visible tbody tr').should('not.exist');
    });

    it('Auto-remove after upload', () => {
        mockUploadResponse();
        local.value.autoRemoveAfterUpload = true;
        cy.mount(App, mountOptions({ isUserAnonymous: false }));

        loadFixture('expAvf', 'videoFileExpAvf');
        loadFixture('intRmv', 'videoFileIntRmv');

        cy.get('input[type=file]').selectFile([
            { contents: '@videoFileExpAvf', fileName: 'exp.avf' },
            { contents: '@videoFileIntRmv', fileName: 'int.rmv' },
        ], { force: true });

        cy.get('table:visible .checkbox-input').first().click(); // 全选
        cy.get('button').contains('Upload').click();

        cy.contains('Uploading').should('not.exist');
        cy.get('table:visible').getTable().should((tableData) => {
            expect(tableData.length).to.equal(1);
            expect(tableData[0]).to.deep.equal({ ...fixtures.intRmv.tableData, Status: 'New identifier' });
        });
    });

    it('Auto-upload after parse', () => {
        mockUploadResponse();
        local.value.autoUploadAfterParse = true;
        cy.mount(App, mountOptions({ isUserAnonymous: false }));

        loadFixture('expAvf', 'videoFileExpAvf');
        loadFixture('intRmv', 'videoFileIntRmv');

        cy.get('input[type=file]').selectFile([
            { contents: '@videoFileExpAvf', fileName: 'exp.avf' },
            { contents: '@videoFileIntRmv', fileName: 'int.rmv' },
        ], { force: true });

        cy.contains('Parsing files').should('not.exist');

        cy.get('table:visible').getTable().should((tableData) => {
            expect(tableData.length).to.equal(2);
            expect(tableData[0]).to.deep.equal({ ...fixtures.expAvf.tableData, Status: 'Success' });
            expect(tableData[1]).to.deep.equal({ ...fixtures.intRmv.tableData, Status: 'New identifier' });
        });
    });

    it('Auto-upload and auto-remove together', () => {
        mockUploadResponse();
        local.value.autoUploadAfterParse = true;
        local.value.autoRemoveAfterUpload = true;
        cy.mount(App, mountOptions({ isUserAnonymous: false }));

        loadFixture('expAvf', 'videoFileExpAvf');
        loadFixture('intRmv', 'videoFileIntRmv');

        cy.get('input[type=file]').selectFile([
            { contents: '@videoFileExpAvf', fileName: 'exp.avf' },
            { contents: '@videoFileIntRmv', fileName: 'int.rmv' },
        ], { force: true });

        cy.contains('Parsing files').should('not.exist');
        cy.get('table:visible').getTable().should((tableData) => {
            expect(tableData.length).to.equal(1);
            expect(tableData[0]).to.deep.equal({ ...fixtures.intRmv.tableData, Status: 'New identifier' });
        });
    });
});
