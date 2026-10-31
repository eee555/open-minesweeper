import { useLocalStorage } from '@vueuse/core';
import { defineStore } from 'pinia';

import { pinia } from './create';

import { fetchProfileSaoleiRecords, profileDataRevision } from '@/services/profileDataService';
import type { TopAnchors } from '@/services/topRankingService';
import { setVideoInfoViewer } from '@/services/videoInfoService';
import { deepMutableCopy } from '@/utils';
import type { PiecewiseColorSchemeInterface } from '@/utils/colors';
import { LoginStatus } from '@/utils/common/structInterface';
import { colorSchemeTemplates } from '@/utils/config';
import type { CellChoice, ColorTemplateName, ColumnChoice, MS_Software } from '@/utils/ms_const';
import { MS_Softwares } from '@/utils/ms_const';
import { UserProfile } from '@/utils/userprofile';
import type { UserProfileData } from '@/utils/userprofile';
import type { getStat_stat } from '@/utils/videoabstract';

interface UserState {
    user: UserProfile;
    player: UserProfile;
    login_status: LoginStatus;
    sessionRevision: number;
    new_identifier: boolean;
    expertTimeMs: number | null | undefined;
    qualificationStatus: 'idle' | 'loading' | 'ready' | 'error';
    qualificationRevision: number;
    topAnchors: TopAnchors | null;
}

export const store = defineStore('user', {
    state: (): UserState => ({
        user: new UserProfile(), // 真正的用户
        // 访问谁的地盘不再具有记忆性。即点“我的地盘”，将永远是“我”的地盘
        // 想要访问特定用户，可以用url
        // 访问谁的地盘
        player: new UserProfile(),
        login_status: LoginStatus.Undefined, // 登录状态，全局维护
        sessionRevision: 0,
        new_identifier: false, // 是否有新标识录像
        expertTimeMs: undefined,
        qualificationStatus: 'idle',
        qualificationRevision: -1,
        topAnchors: null,
    }),
    getters: {
        isSelf: (state) => state.user.id === state.player.id && state.user.id !== 0,
        isUserAnonymous: (state) => state.user.isAnonymous,
        expTimeMs: (state) => state.expertTimeMs ?? 999999,
    },
    actions: {
        login(userdata: UserProfileData) {
            this.sessionRevision++;
            this.user = new UserProfile(userdata);
            setVideoInfoViewer(this.user.id, this.sessionRevision);
            this.expertTimeMs = undefined;
            this.qualificationStatus = 'idle';
            this.qualificationRevision = -1;
            this.login_status = LoginStatus.IsLogin;
        },
        logout() {
            this.sessionRevision++;
            this.user = new UserProfile();
            setVideoInfoViewer(0, this.sessionRevision);
            this.expertTimeMs = undefined;
            this.qualificationStatus = 'idle';
            this.qualificationRevision = -1;
            this.login_status = LoginStatus.NotLogin;
        },
        async loadQualification() {
            const owner = this.user;
            const revision = profileDataRevision(owner.id);
            if (this.login_status !== LoginStatus.IsLogin || owner.id < 1) return;
            if (this.qualificationRevision === revision && (this.qualificationStatus === 'loading' || this.qualificationStatus === 'ready')) return;
            this.qualificationRevision = revision;
            this.qualificationStatus = 'loading';
            this.expertTimeMs = undefined;
            try {
                const records = await fetchProfileSaoleiRecords(owner.id);
                if (this.user !== owner || profileDataRevision(owner.id) !== revision) return;
                this.expertTimeMs = records.saolei.et;
                this.qualificationStatus = 'ready';
            } catch {
                if (this.user === owner && profileDataRevision(owner.id) === revision) this.qualificationStatus = 'error';
            }
        },
    },
})(pinia);

export const videoplayerstore = defineStore('videoplayer', {
    state: () => ({
        visible: false,
        id: 0,
        url: '',
    }),
})(pinia);

export { local } from './local';
export type { LocalSettings } from './local';

export const videoPlayerConfig = useLocalStorage(
    'video-player-config',
    {
        cellSize: 24,
        showProbability: true,
        probabilityColorScheme: {
            colors: ['#15803d', '#0f766e', '#2563eb', '#b45309', '#dc2626', '#7f1d1d'],
            thresholds: [10, 25, 50, 75, 90],
        },
    },
    { mergeDefaults: true },
);

// Drop settings belonging to removed external replay players.
Reflect.deleteProperty(videoPlayerConfig.value, 'backend');
Reflect.deleteProperty(videoPlayerConfig.value, 'strangeDustTrust');

export const videofilter = useLocalStorage('videofilter', {
    pagesize: 100,
    level: 'e',
    filter_state: ['a', 'b', 'c', 'd'],
    bbbv_range: {
        b: [2, 54],
        i: [30, 216],
        e: [100, 381],
    },
});

const defaultColorSchemes: Record<keyof typeof colorSchemeTemplates.ArbiterStatsAuto, PiecewiseColorSchemeInterface> = deepMutableCopy(colorSchemeTemplates.ArbiterStatsAuto);

export const colorTheme = useLocalStorage(
    'colorTheme',
    {
        ...defaultColorSchemes,
        level: {
            b: '#dc2626',
            i: '#16a34a',
            e: '#2563eb',
            c: '#d97706',
        },
    },
    { mergeDefaults: true },
);

export const activityCalendarConfig = useLocalStorage(
    'activity-calendar-config',
    {
        cellSize: 14,
        cellMargin: 3,
        showDate: false,
        useEndTime: false,
    },
    { mergeDefaults: true },
);

export const BBBvSummaryConfig = useLocalStorage(
    'bbbv-summary-config',
    {
        template: 'time' as ColorTemplateName,
        sortBy: 'timems' as getStat_stat,
        displayBy: 'time' as CellChoice,
        sortDesc: false,
        softwareFilter: [...MS_Softwares] as MS_Software[],
        zoom: 1,
        showIcon: 'software' as '' | 'software' | 'state',
        newThresh: 1,
        newDateField: 'upload_time' as 'upload_time' | 'end_time',
    },
    { mergeDefaults: true },
);

export const VideoScatterAxisChoice = ['time', 'bv', 'bvs', 'stnb', 'ioe', 'thrp', 'corr', 'ces', 'cls', 'cl', 'ce', 'rqp'] as const;
export type VideoScatterAxisChoice = typeof VideoScatterAxisChoice[number];
export const VideoScatterColorByChoice = ['level', 'time', 'bvs', 'stnb', 'ioe', 'thrp', 'ces', 'cls'] as const;
export type VideoScatterColorByChoice = typeof VideoScatterColorByChoice[number];
export const VideoScatterConfig = useLocalStorage(
    'video-scatter-config',
    {
        radius: 3,
        x: 'bv' as VideoScatterAxisChoice,
        y: 'time' as VideoScatterAxisChoice,
        colorBy: 'level' as VideoScatterColorByChoice,
        highlightSelected: false,
        showOnlySelected: false,
    },
    { mergeDefaults: true },
);

export const VideoListConfig = useLocalStorage(
    'video-list-config',
    {
        profile: ['state', 'upload_time', 'software', 'level', 'mode', 'time', 'bv', 'bvs', 'ioe', 'thrp', 'path', 'file_size'] as ColumnChoice[],
        tournament: ['state', 'upload_time', 'software', 'level', 'mode', 'time', 'bv', 'bvs', 'ioe', 'thrp', 'path'] as ColumnChoice[],
    },
    { mergeDefaults: true },
);
