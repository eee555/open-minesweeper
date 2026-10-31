import type { RouteRecordRaw } from 'vue-router';

export const staffRoutes: RouteRecordRaw[] = [
    {
        path: 'medals',
        name: 'staff-medals',
        component: () => import('./Medal.vue'),
    },
    {
        path: 'userprofile',
        name: 'staff-userprofile',
        component: () => import('./UserProfile.vue'),
    },
    {
        path: 'videomodel',
        name: 'staff-videomodel',
        component: () => import('./VideoModel.vue'),
    },
    {
        path: 'accountlink',
        name: 'staff-accountlink',
        component: () => import('./AccountLink.vue'),
    },
    {
        path: 'identifier',
        name: 'staff-identifier',
        component: () => import('./Identifier.vue'),
    },
    {
        path: 'logs',
        name: 'staff-logs',
        component: () => import('./Logs.vue'),
    },
    {
        path: 'tournament',
        name: 'staff-tournament',
        component: () => import('./Tournament.vue'),
    },
    {
        path: 'weekly-tournament',
        name: 'staff-weekly-tournament',
        component: () => import('./WeeklyTournament.vue'),
    },
    {
        path: 'task',
        name: 'staff-task',
        component: () => import('./Task.vue'),
    },
    {
        path: 'batchvideo',
        name: 'staff-batchvideo',
        component: () => import('./BatchUpdateVideo.vue'),
    },
    {
        path: 'batchpluck',
        name: 'staff-batchpluck',
        component: () => import('./BatchRefreshPLuck.vue'),
    },
    {
        path: 'ranking-repair',
        name: 'staff-ranking-repair',
        component: () => import('./RankingRepair.vue'),
    },
    {
        path: 'minigame',
        name: 'staff-minigame',
        component: () => import('./Minigame.vue'),
    },
];
