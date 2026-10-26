const HOST = {
    id: 48,
    username: 'gscHost',
    email: 'gscHost@email.com',
    password: 'gscHostPassword',
} as const;

const STAFF = {
    id: 1,
    username: 'staff',
    email: 'staff@email.com',
    password: 'staffPassword',
    realname: '周赛管理员',
} as const;

const USER = {
    id: 2,
    username: 'user',
    email: 'user@email.com',
    password: 'userPassword',
    realname: '周赛用户',
} as const;

const GSC_TOKEN = 'G1234' as const;
const ARBITER_IDENTIFIER = `Guo Jin Yang ${GSC_TOKEN}` as const;
let weeklyFinishTaskRunAfter = '';

interface DangerzoneTournament {
    id: number;
    subclass: 'g';
    state: string;
    start_time: string;
    end_time: string;
    host_id: number;
    data: {
        order: number;
        token: string;
    };
}

interface DangerzoneWeeklyTournament {
    id: number;
    start_time: string;
    end_time: string;
}

interface ParticipantWindow {
    startText: string;
    endText: string;
    start: Date;
    end: Date;
}

interface BackgroundTaskRow {
    task_path: string;
    status: string;
    run_after: string;
}

function createTournament(order: number, state: string) {
    return cy.dangerzonePost<DangerzoneTournament>('create_gsc_tournament', {
        order,
        state,
        start_time: '2000-01-01T00:00:00+08:00',
        end_time: '2099-01-01T00:00:00+08:00',
        token: `G${order.toString().padStart(5, '0')}`,
        host_id: HOST.id,
    });
}

function createWeeklyTournament(options: {
    year: number;
    week: number;
    startTime: Date;
    endTime: Date;
}) {
    return cy.dangerzonePost<DangerzoneWeeklyTournament>('create_weekly_tournament', {
        year: options.year,
        week: options.week,
        start_time: options.startTime.toISOString(),
        end_time: options.endTime.toISOString(),
        host_id: STAFF.id,
    }).then((response) => response.body);
}

function pad(value: number) {
    return value.toString().padStart(2, '0');
}

function displayDateTime(date: Date) {
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function parseDisplayDateTime(value: string) {
    const match = (/(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})/).exec(value);
    expect(match, `datetime in ${value}`).to.not.equal(null);
    if (match === null) throw new Error(`datetime not found in ${value}`);
    const [, year, month, day, hour, minute, second] = match;
    return new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second));
}

function visitGSCAdmin(gscID: number) {
    cy.visit('/#/gsc/admin/');
    cy.contains('第').next().find('input').invoke('val', '');
    cy.contains('第').next().find('input').type(`${gscID}{enter}`);
}

function setDateTime(dateStr: string, timeStr: string) {
    cy.get('[placeholder="Select date"]').filter(':visible').type(`${dateStr}{enter}`);
    cy.get('[placeholder="Select time"]').filter(':visible').invoke('val', '');
    cy.get('[placeholder="Select time"]').filter(':visible').type(`${timeStr}{enter}`);
    cy.get('button:visible').contains('OK').click();
}

function setStartDateTime(dateStr: string, timeStr: string) {
    cy.contains('设置开始时间：').next().click();
    setDateTime(dateStr, timeStr);
    cy.contains('操作成功');
    cy.closeElNotifications();
}

function setEndDateTime(dateStr: string, timeStr: string) {
    cy.contains('设置结束时间：').next().click();
    setDateTime(dateStr, timeStr);
    cy.contains('操作成功');
    cy.closeElNotifications();
}

function assertTableData(expected: Record<string, unknown>[], exact = true) {
    // getTable() takes a one-time snapshot, so wait for the expected DOM rows first.
    assertVisibleTournamentNames(expected.map((row) => String(row.比赛)), exact);
    cy.get('table:visible').getTable().should((tableData) => {
        if (exact) {
            expect(tableData).to.have.length(expected.length);
        }
        expected.forEach((exp) => {
            const row = tableData.find((item) => item.比赛 === exp.比赛);
            expect(row, `row for ${String(exp.比赛)}`).to.not.equal(undefined);
            Object.keys(exp).forEach((key) => {
                expect(row?.[key]).to.equal(exp[key]);
            });
        });
    });
}

function assertVisibleTournamentNames(expectedNames: string[], exact = true) {
    cy.get('.el-table:visible').first().within(() => {
        expectedNames.forEach((name) => {
            cy.contains('.el-table__row', name).should('be.visible');
        });
        cy.get('.el-table__row').should((rows) => {
            const names = [...rows].map((row) => row.textContent ?? '');
            if (exact) expect(names).to.have.length(expectedNames.length);
            expectedNames.forEach((name) => {
                expect(names.some((rowText) => rowText.includes(name))).to.equal(true);
            });
        });
    });
}

function selectHomepageListTab(name: string) {
    cy.contains('.el-tabs__item', name).click();
    cy.contains('.el-tabs__item.is-active', name).should('be.visible');
}

function registerOnWeeklyTournamentPage(tournamentId: number) {
    cy.intercept('GET', '**/api/tournament/participants*').as('weeklyParticipants');
    cy.intercept('POST', '**/api/tournament/weekly/participant').as('createWeeklyParticipant');
    cy.intercept('GET', '**/api/tournament/get_videos/participant*').as('weeklyParticipantVideosAfterRegister');

    cy.login(USER.username, USER.password);
    cy.visit(`/#/tournament/${tournamentId}`);
    cy.wait('@weeklyParticipants').its('response.statusCode').should('eq', 200);

    cy.contains('进行中');
    cy.contains('即时成绩').should('not.exist');
    cy.contains('如何参赛').next().within(() => {
        cy.contains('button', '开始打卡').click();
    });
    cy.contains('.el-dialog', '准备好了吗？').within(() => {
        cy.contains('操作不可撤回');
        cy.contains('button', '确认').click();
    });
    cy.wait('@createWeeklyParticipant').its('response.statusCode').should('eq', 200);
    cy.wait('@weeklyParticipantVideosAfterRegister').its('response.statusCode').should('eq', 200);

    cy.contains('操作成功');
    cy.closeElNotifications();
    cy.get('[data-cy=weekly-participant-window]').should('be.visible');
    cy.contains('即时成绩').should('be.visible');
}

function getParticipantWindow() {
    return cy.get('[data-cy=weekly-participant-window]').invoke('text').then((text) => {
        const matches = [...text.matchAll(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/g)].map((match) => match[0]);
        expect(matches).to.have.length(2);
        return {
            startText: matches[0],
            endText: matches[1],
            start: parseDisplayDateTime(matches[0]),
            end: parseDisplayDateTime(matches[1]),
        };
    });
}

function getVisibleToken() {
    return cy.get('.ttfamily').first().invoke('text').then((text) => text.trim());
}

function readDescriptionValue(label: string) {
    return cy.contains('.el-descriptions__label', label).next().invoke('text').
        then((text) => text.trim());
}

before(() => {
    cy.flushDatabase();
    cy.registerUsers([HOST, STAFF, USER]);
    cy.setStaff(STAFF.id);
});

beforeEach(() => {
    cy.mockPlayerNameFallback();
});

describe('Tournament page backed by real API data', () => {
    let normalTournament: DangerzoneTournament;

    before(() => {
        createTournament(21, 'n').then((response) => {
            normalTournament = response.body;
        });
        createTournament(22, 'a');
        createTournament(23, 'p');
        createTournament(24, 'c');
    });

    it('loads each homepage category tab from the backend', () => {
        cy.visit('/#/tournament/');

        cy.contains('.el-tabs__item.is-active', '正常').should('be.visible');
        assertVisibleTournamentNames(['第21届金羊杯']);

        cy.contains('.el-tabs__item', '已颁奖').click();
        assertVisibleTournamentNames(['第22届金羊杯']);

        cy.contains('.el-tabs__item', '其他').click();
        assertVisibleTournamentNames(['第23届金羊杯', '第24届金羊杯']);

        cy.contains('.el-tabs__item', '全部').click();
        assertVisibleTournamentNames(['第21届金羊杯', '第22届金羊杯', '第23届金羊杯', '第24届金羊杯']);
    });

    it('opens tournament detail as a standalone route from the list', () => {
        cy.then(() => {
            const { id, data } = normalTournament;
            cy.visit('/#/tournament/');
            cy.contains('.el-table__row', `第${data.order}届金羊杯`).click();

            cy.location('hash').should('eq', `#/tournament/${id}`);
            cy.contains('h1', `第${data.order}届金羊杯`).should('be.visible');

            cy.visit('/#/tournament/');
            cy.location('hash').should('eq', '#/tournament/');
            cy.contains('.el-tabs__item.is-active', '正常').should('be.visible');
            cy.contains('.el-tabs__item', `第${data.order}届金羊杯`).should('not.exist');

            cy.contains('.el-table__row', `第${data.order}届金羊杯`).click();
            cy.location('hash').should('eq', `#/tournament/${id}`);
        });
    });
});

describe('GSC tournament', () => {
    it('Create GSC', () => {
        cy.login(HOST.username, HOST.password);
        cy.visit('/#/gsc/admin/');

        cy.contains('请输入非零届数');
        cy.contains('第').next().find('input').type('2{enter}');
        cy.contains('未找到该届信息');
        cy.contains('创建比赛').click();
        cy.contains('操作成功');
        cy.closeElNotifications();

        cy.contains('开始时间：未设置');
        cy.contains('结束时间：未设置');
        cy.contains('标识：未设置');
        cy.contains('结算后台任务');
        cy.contains('NULL');
    });

    it('Set start time', () => {
        cy.login(HOST.username, HOST.password);
        visitGSCAdmin(2);

        cy.contains('开始时间：未设置');
        setStartDateTime('2100-01-01', '00:00:00');
        cy.contains('开始时间：2100-01-01 00:00:00');

        cy.visit('/#/tournament/');
        selectHomepageListTab('其他');
        cy.contains('第2届金羊杯').should('be.visible');
        cy.get('table:visible').getTable().should((tableData) => {
            const tournament = tableData.find((row) => row.比赛 === '第2届金羊杯');
            expect(tournament?.开始时间).to.equal('2100-01-01 00:00:00');
        });
    });

    it('Set end time', () => {
        cy.login(HOST.username, HOST.password);
        visitGSCAdmin(2);

        cy.contains('结束时间：未设置');
        setEndDateTime('2100-01-02', '00:00:00');
        cy.contains('结束时间：2100-01-02 00:00:00');

        cy.visit('/#/tournament/');
        selectHomepageListTab('其他');
        cy.contains('第2届金羊杯').should('be.visible');
        cy.get('table:visible').getTable().should((tableData) => {
            const tournament = tableData.find((row) => row.比赛 === '第2届金羊杯');
            expect(tournament?.结束时间).to.equal('2100-01-02 00:00:00');
        });
    });

    it('Reset start time', () => {
        cy.login(HOST.username, HOST.password);

        visitGSCAdmin(2);
        cy.contains('开始时间：2100-01-01 00:00:00');
        setStartDateTime('2099-12-31', '00:00:00');
        cy.contains('开始时间：2099-12-31 00:00:00');

        cy.visit('/#/tournament/');
        selectHomepageListTab('其他');
        cy.contains('第2届金羊杯').should('be.visible');
        cy.get('table:visible').getTable().should((tableData) => {
            const tournament = tableData.find((row) => row.比赛 === '第2届金羊杯');
            expect(tournament?.开始时间).to.equal('2099-12-31 00:00:00');
        });
    });

    it('Reset end time', () => {
        cy.login(HOST.username, HOST.password);
        visitGSCAdmin(2);
        cy.contains('结束时间：2100-01-02 00:00:00');
        setEndDateTime('2100-01-03', '00:00:00');
        cy.contains('结束时间：2100-01-03 00:00:00');

        cy.visit('/#/tournament/');
        selectHomepageListTab('其他');
        cy.contains('第2届金羊杯').should('be.visible');
        cy.get('table:visible').getTable().should((tableData) => {
            const tournament = tableData.find((row) => row.比赛 === '第2届金羊杯');
            expect(tournament?.结束时间).to.equal('2100-01-03 00:00:00');
        });
    });

    it('Create more GSC for tests', () => {
        cy.login(HOST.username, HOST.password);
        visitGSCAdmin(3);
        cy.contains('创建比赛').click();
        cy.contains('操作成功');
        cy.closeElNotifications();

        setStartDateTime('2000-01-01', '00:00:00');
        setEndDateTime('2100-01-01', '00:00:00');

        visitGSCAdmin(4);
        cy.contains('创建比赛').click();
        cy.contains('操作成功');
        cy.closeElNotifications();
        setStartDateTime('2000-01-01', '00:00:00');
        setEndDateTime('2000-01-02', '00:00:00');

        cy.visit('/#/tournament/');
        selectHomepageListTab('其他');
        cy.contains(`用户#${HOST.id}`);

        assertTableData([
            { 状态: '审核中', 比赛: '第2届金羊杯', 主办方: `用户#${HOST.id}`, 开始时间: '2099-12-31 00:00:00', 结束时间: '2100-01-03 00:00:00' },
            { 状态: '审核中', 比赛: '第4届金羊杯', 主办方: `用户#${HOST.id}`, 开始时间: '2000-01-01 00:00:00', 结束时间: '2000-01-02 00:00:00' },
            { 状态: '审核中', 比赛: '第3届金羊杯', 主办方: `用户#${HOST.id}`, 开始时间: '2000-01-01 00:00:00', 结束时间: '2100-01-01 00:00:00' },
        ], false);
    });

    it('Admin validate', () => {
        cy.login(STAFF.username, STAFF.password);
        cy.visit('/#/staff/tournament');

        cy.contains('比赛 ID').get('input').filter(':visible').clear();
        cy.contains('比赛 ID').get('input').filter(':visible').type('5{enter}');
        cy.get('button').filter(':visible').contains('查询').click();
        cy.contains('第2届金羊杯');
        cy.contains('审核中');
        cy.get('button[aria-label="取消审核"]').click();
        cy.contains('已取消');

        cy.get('button[aria-label="通过审核"]').click();
        cy.contains('即将开始');

        cy.contains('比赛 ID').get('input').filter(':visible').clear();
        cy.contains('比赛 ID').get('input').filter(':visible').type('6{enter}');
        cy.get('button').filter(':visible').contains('查询').click();
        cy.contains('第3届金羊杯');
        cy.contains('审核中');
        cy.get('button[aria-label="通过审核"]').click();
        cy.contains('进行中');

        cy.contains('比赛 ID').get('input').filter(':visible').clear();
        cy.contains('比赛 ID').get('input').filter(':visible').type('7{enter}');
        cy.get('button').filter(':visible').contains('查询').click();
        cy.contains('第4届金羊杯');
        cy.contains('审核中');
        cy.get('button[aria-label="通过审核"]').click();
        cy.contains('结算中');
    });

    it('Tournament Page', () => {
        cy.visit('/#/tournament/');
        cy.contains(`用户#${HOST.id}`);

        cy.contains('.el-tabs__item.is-active', '正常').should('be.visible');
        assertVisibleTournamentNames(['第21届金羊杯', '第2届金羊杯', '第3届金羊杯', '第4届金羊杯']);

        selectHomepageListTab('已颁奖');
        assertVisibleTournamentNames(['第22届金羊杯']);

        selectHomepageListTab('全部');
        assertTableData([
            { 状态: '即将开始', 比赛: '第2届金羊杯', 主办方: `用户#${HOST.id}`, 开始时间: '2099-12-31 00:00:00', 结束时间: '2100-01-03 00:00:00' },
            { 状态: '结算中', 比赛: '第4届金羊杯', 主办方: `用户#${HOST.id}`, 开始时间: '2000-01-01 00:00:00', 结束时间: '2000-01-02 00:00:00' },
            { 状态: '进行中', 比赛: '第3届金羊杯', 主办方: `用户#${HOST.id}`, 开始时间: '2000-01-01 00:00:00', 结束时间: '2100-01-01 00:00:00' },
        ], false);
    });

    it('Modify visible token for ongoing GSC', () => {
        cy.login(HOST.username, HOST.password);
        visitGSCAdmin(3);
        cy.contains('span', /^标识：G\d{5}$/).should('exist');
        cy.contains('设置标识：').next().find('input').type(`${GSC_TOKEN}{enter}`);
        cy.contains('修改').click();
        cy.contains('操作成功');
        cy.closeElNotifications();
        cy.contains('span', `标识：${GSC_TOKEN}`).should('exist');
    });

    it('Preparing Tournament', () => {
        cy.login(USER.username, USER.password);
        cy.intercept('POST', '**/api/tournament/gsc/participant').as('registerPreparingGSC');
        cy.intercept('GET', '**/api/tournament/participants*').as('preparingParticipants');
        cy.visit('/#/tournament/5');
        cy.wait('@preparingParticipants');
        cy.contains('即将开始');
        cy.contains('如何参赛').next().within(() => {
            cy.contains('查看参赛说明').should('have.attr', 'href').and('include', '/docs/guide/gsc');
            cy.contains('button', '注册').should('be.enabled').click();
        });
        cy.wait('@registerPreparingGSC').its('response.statusCode').should('eq', 200);
        cy.wait('@preparingParticipants').its('response.statusCode').should('eq', 200);
        cy.closeElNotifications();
        cy.contains('已报名，比赛开始后公布比赛标识并开放 Arbiter 标识注册。').should('be.visible');
        cy.contains('[data-cy=gsc-participants] .el-tag', `用户#${USER.id}`).should('be.visible');
        cy.get('[data-cy=gsc-participants] button').should('not.exist');
        cy.get('.ttfamily, input[placeholder="标识"], #tab-personal').should('not.exist');

        cy.visit('/#/tournament/6');
        cy.contains('进行中');
    });

    it('Ongoing Tournament registration', () => {
        cy.login(USER.username, USER.password);
        cy.visit('/#/tournament/6');
        cy.contains('进行中');
        cy.contains('即时成绩').should('not.exist');
        cy.contains('如何参赛').next().within(() => {
            cy.contains('button', '注册').click();
        });
        cy.contains('操作成功');
        cy.closeElNotifications();
        cy.contains('即时成绩').should('be.visible');

        cy.contains('如何参赛').next().within(() => {
            cy.contains('比赛标识：');
            cy.contains(GSC_TOKEN);
            cy.get('input[placeholder="标识"]').type(ARBITER_IDENTIFIER);
            cy.contains('button', '注册').click();
        });
        cy.contains('操作成功');
        cy.closeElNotifications();

        cy.contains('如何参赛').next().within(() => {
            cy.contains('Arbiter参赛标识：');
            cy.contains(ARBITER_IDENTIFIER);
        });
        cy.contains('即时成绩');
    });
});

describe('Weekly tournament', () => {
    it('registers participants with a two-hour window capped by tournament end time', () => {
        const now = new Date();
        now.setMilliseconds(0);
        const fullWindowStart = new Date(now.getTime() - 60 * 60 * 1000);
        const fullWindowEnd = new Date(now.getTime() + 24 * 60 * 60 * 1000);
        const truncatedStart = new Date(now.getTime() - 60 * 60 * 1000);
        const truncatedEnd = new Date(now.getTime() + 30 * 60 * 1000);
        let tournamentId = 0;

        createWeeklyTournament({
            year: 2099,
            week: 1,
            startTime: fullWindowStart,
            endTime: fullWindowEnd,
        }).then((tournament) => {
            tournamentId = tournament.id;
        });
        cy.then(() => {
            registerOnWeeklyTournamentPage(tournamentId);
        });
        getParticipantWindow().then((window) => {
            expect(window.end.getTime() - window.start.getTime()).to.equal(2 * 60 * 60 * 1000);
        });

        createWeeklyTournament({
            year: 2099,
            week: 2,
            startTime: truncatedStart,
            endTime: truncatedEnd,
        }).then((tournament) => {
            tournamentId = tournament.id;
        });
        cy.then(() => {
            registerOnWeeklyTournamentPage(tournamentId);
        });
        getParticipantWindow().then((window) => {
            expect(window.endText).to.equal(displayDateTime(truncatedEnd));
        });
    });

    it('checks in only videos uploaded within the participant window with the participant token', () => {
        const now = new Date();
        now.setMilliseconds(0);
        const tournamentStart = new Date(now.getTime() - 60 * 60 * 1000);
        const tournamentEnd = new Date(now.getTime() + 24 * 60 * 60 * 1000);
        let tournamentId = 0;
        let token = '';
        let participantWindow: ParticipantWindow;

        createWeeklyTournament({
            year: 2099,
            week: 3,
            startTime: tournamentStart,
            endTime: tournamentEnd,
        }).then((tournament) => {
            tournamentId = tournament.id;
        });
        cy.then(() => {
            registerOnWeeklyTournamentPage(tournamentId);
        });
        getVisibleToken().then((visibleToken) => {
            token = visibleToken;
        });
        getParticipantWindow().then((window) => {
            participantWindow = window;
        });

        cy.then(() => {
            expect(token).to.not.equal('');
            const validUpload = new Date(participantWindow.start.getTime() + 30 * 60 * 1000);
            return cy.createVideo({
                user_id: USER.id,
                identifier: 'weekly-valid',
                tournament_identifier: [token],
                upload_time: validUpload.toISOString(),
                state: 'c',
                level: 'i',
                timems: 12000,
                bv: 80,
            });
        }).then((response) => {
            expect(response.body.id).to.be.greaterThan(0);
            expect(response.body.ongoing_tournament).to.equal(true);
            expect(response.body.tournament_ids).to.include(tournamentId);
        });

        cy.then(() => {
            const validUpload = new Date(participantWindow.start.getTime() + 30 * 60 * 1000);
            return cy.createVideo({
                user_id: USER.id,
                identifier: 'weekly-wrong-token',
                tournament_identifier: ['WRONG_TOKEN'],
                upload_time: validUpload.toISOString(),
                state: 'c',
                level: 'i',
                timems: 13000,
                bv: 80,
            });
        }).then((response) => {
            expect(response.body.id).to.be.greaterThan(0);
            expect(response.body.ongoing_tournament).to.equal(false);
            expect(response.body.tournament_ids).to.not.include(tournamentId);
        });

        cy.then(() => {
            const lateUpload = new Date(participantWindow.end.getTime() + 60 * 1000);
            return cy.createVideo({
                user_id: USER.id,
                identifier: 'weekly-late',
                tournament_identifier: [token],
                upload_time: lateUpload.toISOString(),
                state: 'c',
                level: 'i',
                timems: 14000,
                bv: 80,
            });
        }).then((response) => {
            expect(response.body.id).to.be.greaterThan(0);
            expect(response.body.ongoing_tournament).to.equal(false);
            expect(response.body.tournament_ids).to.not.include(tournamentId);
        });

        cy.intercept('GET', '**/api/tournament/get_videos/participant*').as('participantVideos');
        cy.contains('[data-cy=tournament-data-tabs] .el-tabs__item', '即时成绩').click();
        cy.get('[data-cy=personal-score-refresh]').click();
        cy.wait('@participantVideos').its('response.statusCode').should('eq', 200);
        cy.contains('.el-tabs__item', '录像').click();
        cy.get('.el-tab-pane:visible').last().within(() => {
            cy.contains('12.000').should('be.visible');
            cy.contains('13.000').should('not.exist');
            cy.contains('14.000').should('not.exist');
        });
    });

    it('lets staff create a weekly tournament and schedule its finish task', () => {
        let startText = '';
        let endText = '';

        cy.intercept('POST', '**/api/tournament/weekly/new').as('createWeeklyTournament');
        cy.login(STAFF.username, STAFF.password);
        cy.visit('/#/staff/weekly-tournament');
        cy.contains('比赛类型');
        cy.contains('.el-select', '2高5中').should('be.visible');
        cy.contains('button', '创建下周打卡赛').click();
        cy.wait('@createWeeklyTournament').its('response.statusCode').should('eq', 200);
        cy.contains('操作成功');
        cy.closeElNotifications();
        cy.contains('创建结果');

        readDescriptionValue('开始时间').then((value) => {
            startText = value;
        });
        readDescriptionValue('结束时间').then((value) => {
            endText = value;
            weeklyFinishTaskRunAfter = value;
        });
        cy.then(() => {
            const start = parseDisplayDateTime(startText);
            const end = parseDisplayDateTime(endText);
            expect(start.getDay()).to.equal(1);
            expect(end.getTime() - start.getTime()).to.equal(7 * 24 * 60 * 60 * 1000);
        });
    });
});

describe('GSC tournament finish task', () => {
    it('Finished Tournament and finish task', () => {
        cy.visit('/#/tournament/7');
        cy.contains('结算中');
        cy.contains('如何参赛').should('not.exist');
        cy.contains('比赛结果').should('not.exist');

        cy.login(HOST.username, HOST.password);
        visitGSCAdmin(4);
        cy.contains('结算后台任务');
        cy.contains('NULL');
        cy.contains('button', '计算排行并结束比赛').click();
        cy.contains('操作成功');
        cy.closeElNotifications();
    });
});

describe('GSC historical supplementation', () => {
    let historyTournamentId = 0;
    let secondHistoryTournamentId = 0;
    let uploadedTournamentId = 0;

    before(() => {
        cy.registerUsers(Array.from({ length: 21 }, (_, index) => {
            const id = 101 + index;
            return { id, username: `history${id}`, email: `history${id}@example.com`, password: 'historyPassword' };
        }));
        for (const order of [19, 20, 18]) {
            cy.dangerzonePost<DangerzoneTournament>('create_gsc_tournament', { order, state: 'a', start_time: '2000-01-01T00:00:00Z', end_time: '2000-01-02T00:00:00Z', host_id: HOST.id }).then(({ body }) => {
                if (order === 19) historyTournamentId = body.id;
                else if (order === 20) secondHistoryTournamentId = body.id;
                else uploadedTournamentId = body.id;
            });
        }
    });

    it('imports CSV scores across tournaments and more than ten rows, then publishes only after explicit recalculation', () => {
        cy.login(HOST.username, HOST.password);
        cy.intercept({ method: 'GET', pathname: '/api/tournament/gsc/results', query: { tournament_id: String(historyTournamentId) } }).as('history');
        cy.intercept('POST', '**/api/tournament/gsc/history/scores/users').as('userBatch');
        cy.intercept('POST', '**/api/tournament/gsc/history/scores/anonymous').as('anonymousBatch');
        visitGSCAdmin(19);
        cy.wait('@history');
        cy.contains('.el-tabs__item', '站内成绩 CSV').click();
        cy.fixture<string>('gsc/type2.csv', 'utf8').then((fixture) => {
            const extra = Array.from({ length: 11 }, (_, i) => [19, 111 + i, 1000, 2000, 40000, 10000, 12000, 130000, 40000, 50000, 230000].join(','));
            const crossOrder = fixture.trim().split(/\r?\n/)[1].replace(/^19,/, '20,');
            const text = `${fixture.trim()}\n${extra.join('\n')}\n${crossOrder}`;
            cy.get('.el-tab-pane:visible [data-cy=history-csv]').selectFile({ contents: Cypress.Buffer.from(text), fileName: 'history-users.csv' });
        });
        cy.get('.el-tab-pane:visible [data-cy=history-csv-submit]').should('contain.text', '22').click();
        cy.wait('@userBatch').its('request.body.rows').should('have.length', 10);
        cy.wait('@userBatch').its('request.body.rows').should('have.length', 10);
        cy.wait('@userBatch').its('request.body.rows').should('have.length', 1);
        cy.wait('@userBatch').its('request.body.order').should('eq', 20);
        cy.get('.el-tab-pane:visible [data-cy=history-csv-progress]').should('contain.text', '22 / 22');
        cy.wait('@history');
        cy.contains('.el-tabs__item', '匿名成绩 CSV').click();
        cy.get('.el-tab-pane:visible [data-cy=history-csv]').selectFile('cypress/fixtures/gsc/type3.csv');
        cy.get('.el-tab-pane:visible [data-cy=history-csv-submit]').click();
        cy.wait('@anonymousBatch').its('response.statusCode').should('eq', 200);
        cy.wait('@history');
        cy.get('[data-cy=history-participants] tbody tr:not(.base-table-empty-row)').should('have.length', 31);
        cy.get('[data-cy=history-participants] table').getTable().should((rows) => {
            expect(rows).to.have.length(31);
            expect(rows.find((row) => row.选手 === 'kiraa96G09511')).to.include({ 成绩来源: '手工', '总成绩 / ms': '319830' });
        });
        cy.then(() => cy.dangerzonePost('refresh_tournament_scores', { id: historyTournamentId }));
        cy.then(() => cy.dangerzonePost('refresh_tournament_scores', { id: secondHistoryTournamentId }));
        cy.then(() => cy.visit(`/#/tournament/${historyTournamentId}`));
        cy.wait('@history');
        cy.get('[data-cy=all-participants-tabs] .el-table__body tbody tr').should('have.length', 31);
        cy.get('[data-cy=all-participants-tabs] .el-table__body').extractTableData().should((rows) => {
            expect(rows).to.have.length(31);
            expect(rows.find((row) => row[0] === 'kiraa96G09511')?.slice(1, 4)).to.deep.equal(['1.470', '1.830', '33.690']);
        });
    });

    it('reuses a replay participant after reloading and imports without the historical race token', () => {
        cy.login(HOST.username, HOST.password);
        cy.intercept({ method: 'GET', pathname: '/api/tournament/gsc/results', query: { tournament_id: String(uploadedTournamentId) } }).as('history');
        cy.intercept('POST', '**/api/tournament/gsc/history/prepare').as('prepareHistory');
        cy.intercept('POST', '**/api/tournament/gsc/history/participants/*/identifier').as('bindHistory');
        cy.intercept('POST', '**/api/tournament/gsc/history/participants/*/videos').as('uploadHistory');
        visitGSCAdmin(18);
        cy.wait('@history');
        cy.get('[data-cy=history-user-id]').type('101');
        cy.get('[data-cy=history-video-files]').selectFile('cypress/fixtures/standard_gsc.evf');
        cy.get('[data-cy=history-identifiers] .el-tag').should('have.length', 1);
        cy.get('[data-cy=history-videos-submit]').click();
        cy.wait('@prepareHistory').its('response.statusCode').should('eq', 200);
        cy.wait('@bindHistory').its('response.statusCode').should('eq', 200);
        cy.wait('@uploadHistory').its('response.statusCode').should('eq', 200);
        cy.wait('@history');
        cy.get('[data-cy=history-participants] tbody tr:not(.base-table-empty-row)').should('have.length', 1);
        cy.get('[data-cy=history-participants] table').getTable().should((rows) => {
            expect(rows).to.have.length(1);
            expect(rows[0]).to.include({ 成绩来源: '录像', 录像: '有' });
        });
        cy.get('[data-cy=history-delete]').should('not.exist');
        visitGSCAdmin(18);
        cy.wait('@history');
        cy.get('[data-cy=history-user-id]').type('101');
        cy.get('[data-cy=history-video-files]').selectFile('cypress/fixtures/standard_gsc.evf');
        cy.get('[data-cy=history-identifiers] .el-tag').should('have.length', 1);
        cy.get('[data-cy=history-videos-submit]').click();
        cy.wait('@prepareHistory').its('response.statusCode').should('eq', 200);
        cy.wait('@bindHistory').its('response.statusCode').should('eq', 200);
        cy.wait('@uploadHistory').its('response.statusCode').should('eq', 200);
        cy.wait('@history');
        cy.get('[data-cy=history-participants] tbody tr:not(.base-table-empty-row)').should('have.length', 1);
        cy.then(() => cy.dangerzonePost('refresh_tournament_scores', { id: uploadedTournamentId }));
        cy.then(() => cy.visit(`/#/tournament/${uploadedTournamentId}`));
        cy.wait('@history');
        cy.get('[data-cy=all-participants-tabs] .el-table__body tbody tr').should('have.length', 1);
        cy.get('[data-cy=all-participants-tabs] .el-table__body').extractTableData().should((rows) => {
            expect(rows).to.have.length(1);
            expect(rows[0].slice(7, 10)).to.deep.equal(['41.021', '240.000', '1001.021']);
        });
    });
});

describe('Tournament background tasks', () => {
    it('shows the scheduled finish tasks at the end', () => {
        let expectedTasks: BackgroundTaskRow[] = [];

        cy.intercept('GET', '**/api/common/tasks/detail').as('taskDetail');
        cy.login(STAFF.username, STAFF.password);
        cy.visit('/#/staff/task');
        cy.contains('button', '加载任务').click();
        cy.wait('@taskDetail').then(({ response }) => {
            expect(response?.statusCode).to.eq(200);
            expectedTasks = (response?.body ?? []) as BackgroundTaskRow[];
            expect(expectedTasks).to.have.length.greaterThan(0);
        });
        cy.get('.p-datatable').find('.el-loading-mask:visible').should('not.exist');
        cy.get('.p-datatable table:visible').getTable().should((tableData) => {
            expect(tableData).to.have.length(expectedTasks.length);

            const weeklyTask = tableData.find((row) => row.任务路径 === 'tournament.weekly.tasks.task_weekly_finish');
            if (expectedTasks.some((task) => task.task_path === 'tournament.weekly.tasks.task_weekly_finish')) {
                expect(weeklyTask?.状态).to.equal('就绪');
                expect(weeklyTask?.最早执行时间).to.equal(weeklyFinishTaskRunAfter);
            }

            const gscTask = tableData.find((row) => row.任务路径 === 'tournament.gsc.tasks.task_gsc_finish');
            if (expectedTasks.some((task) => task.task_path === 'tournament.gsc.tasks.task_gsc_finish')) {
                expect(gscTask?.状态).to.equal('就绪');
            }
        });
    });
});

export {};
