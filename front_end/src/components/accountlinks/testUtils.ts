import PrimeVue from 'primevue/config';
import type { Component } from 'vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { AccountLinkUpdateResponse } from '@/services/accountLinkService';
import { store } from '@/store';
import { pinia } from '@/store/create';
import type {
    AccountBilibiliResponse,
    AccountLinksResponse,
    AccountMineracerResponse,
    AccountMSGamesResponse,
    AccountSaoleiResponse,
    AccountWoMResponse,
    MineracerAccountLinkSessionResponse,
} from '@/utils/accountlinks';
import { AccountLinkPlatform } from '@/utils/accountlinks';
import { UserProfile } from '@/utils/userprofile';

function mountOptions(props: Record<string, unknown>, components: Record<string, Component>) {
    return {
        props,
        global: {
            plugins: [i18n, pinia, PrimeVue],
            components,
            config: {
                globalProperties: {
                    $axios,
                },
            },
        },
    };
}

export function mountAccountLink(component: Component, props: Record<string, unknown> = {}, components: Record<string, Component> = {}): Cypress.Chainable<unknown> {
    return cy.mount(component as never, mountOptions(props, components) as never) as Cypress.Chainable<unknown>;
}

export function resetAccountLinkStore(userId = 1, playerId = 1): void {
    store.user = new UserProfile();
    store.player = new UserProfile();
    store.user.id = userId;
    store.player.id = playerId;
}

export function mockSaoleiResponse(overrides: Partial<AccountSaoleiResponse> = {}): AccountSaoleiResponse {
    return {
        id: 101,
        parent: 1,
        update_time: '2025-01-05T08:09:10Z',
        video_import_task: null,
        name: 'Saolei Player',
        total_views: 9876,
        beg_count: 12,
        int_count: 8,
        exp_count: 4,
        b_t_ms: 12340,
        i_t_ms: 45670,
        e_t_ms: 99990,
        s_t_ms: 158000,
        b_b_cent: 20,
        i_b_cent: 30,
        e_b_cent: 40,
        s_b_cent: 90,
        ...overrides,
    };
}

export function mockMSGamesResponse(overrides: Partial<AccountMSGamesResponse> = {}): AccountMSGamesResponse {
    return {
        id: 202,
        parent: 2,
        update_time: '2025-02-06T09:10:11Z',
        name: 'AM Player',
        local_name: 'Local AM',
        joined: '2024-01-01',
        country: 'China',
        state: 'Example region',
        hand: 'Right',
        mouse: 'Example mouse',
        video_update_time: null,
        ...overrides,
    };
}

export function mockWoMResponse(overrides: Partial<AccountWoMResponse> = {}): AccountWoMResponse {
    return {
        id: 303,
        parent: 3,
        update_time: '2025-03-07T10:11:12Z',
        trophy: 123,
        experience: 456,
        arena_point: 14,
        max_difficulty: 15,
        win: 16,
        last_season: 17,
        b_t_ms: 12000,
        i_t_ms: 45000,
        e_t_ms: 99000,
        b_ioe: 1.23,
        i_ioe: 2.34,
        e_ioe: 3.45,
        b_mastery: 88,
        i_mastery: 77,
        e_mastery: 66,
        b_winstreak: 5,
        i_winstreak: 6,
        e_winstreak: 7,
        b_endurance_ms: 582000,
        i_endurance_ms: 2591000,
        e_endurance_ms: 13888000,
        b_ng_t_ms: 1282,
        i_ng_t_ms: 16720,
        e_ng_t_ms: 48877,
        b_win: 100,
        i_win: 200,
        e_win: 300,
        b_ng_win: 10,
        i_ng_win: 20,
        e_ng_win: 30,
        experience_total: 1000,
        minecoin_total: 2000,
        gem_total: 3000,
        arena_coin_total: 0,
        game_count: 111645,
        win_nf: 16207,
        play_time_ms: 7200000,
        arena_play_time_ms: 3600000,
        bbbv_total: 5060476,
        season_count: 16,
        ...overrides,
    };
}

export function mockBilibiliResponse(overrides: Partial<AccountBilibiliResponse> = {}): AccountBilibiliResponse {
    return {
        id: 404,
        parent: 4,
        update_time: '2025-04-08T11:12:13Z',
        name: 'Bili Player',
        face: 'http://i2.hdslb.com/bfs/app/avatar.png',
        sign: 'Keep mining',
        level: 6,
        following: 11,
        follower: 22,
        video_count: 33,
        article_count: 44,
        opus_count: 55,
        official_title: 'Official Miner',
        ...overrides,
    };
}

export function mockMineracerResponse(overrides: Partial<AccountMineracerResponse> = {}): AccountMineracerResponse {
    return {
        id: '123456789',
        parent: 5,
        update_time: '2025-05-09T12:13:14Z',
        ...overrides,
    };
}

export function mockMineracerAccountLinkSessionResponse(overrides: Partial<MineracerAccountLinkSessionResponse> = {}): MineracerAccountLinkSessionResponse {
    return {
        session_id: 'mineracer-session-1',
        status: 'pending',
        user_code: 'ABCD-EFGH',
        verification_uri: 'https://mineracer.com/link',
        verification_uri_complete: 'https://mineracer.com/link?code=ABCD-EFGH',
        expires_at: '2025-05-09T12:23:14Z',
        next_poll_at: '2025-05-09T12:13:17Z',
        remote_userid: '',
        error_category: '',
        ...overrides,
    };
}

export function mockAccountLinksResponse(): AccountLinksResponse {
    return {
        summary: [
            { id: 1, platform: AccountLinkPlatform.Bilibili, identifier: '404', userprofile: 1, verified: true },
            { id: 2, platform: AccountLinkPlatform.WoM, identifier: '303', userprofile: 1, verified: true },
            { id: 3, platform: AccountLinkPlatform.MSGames, identifier: '202', userprofile: 1, verified: true },
            { id: 4, platform: AccountLinkPlatform.Saolei, identifier: '101', userprofile: 1, verified: true },
            { id: 5, platform: AccountLinkPlatform.Mineracer, identifier: '123456789', userprofile: 1, verified: true },
        ],
        B: mockBilibiliResponse(),
        x: null,
        m: mockMineracerResponse(),
        c: mockSaoleiResponse(),
        a: mockMSGamesResponse(),
        w: mockWoMResponse(),
        q: null,
    };
}

export function mockSaoleiImportSummary(): void {
    cy.intercept('GET', '**/accountlink/saolei/videoimport/stat/**', {
        statusCode: 200,
        body: {
            bulk_task_status: 'NULL',
            total: 3,
            old_imported: 1,
            new_total: 2,
            new_ready: 0,
            new_success: 1,
            new_failed: 0,
            new_connection: 0,
        },
    }).as('importSummary');
}

export function mockUpdateAccountLink(body: AccountLinkUpdateResponse = { type: 'success' }): void {
    cy.intercept('POST', '**/accountlink/update/', {
        statusCode: 200,
        body,
    }).as('updateAccountLink');
}
