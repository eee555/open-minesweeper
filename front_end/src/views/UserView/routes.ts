import type { RouteRecordRaw } from 'vue-router';

export const userRoutes: RouteRecordRaw[] = [
    {
        path: 'settings',
        name: 'user-settings',
        component: () => import('./UserSettingsView.vue'),
    },
    {
        path: 'accountlink',
        name: 'user-accountlink',
        component: () => import('./UserAccountLinkView.vue'),
    },
    {
        path: 'record',
        name: 'user-record',
        component: () => import('./UserRecordView/App.vue'),
    },
    {
        path: 'summary',
        redirect: { name: 'user-top' },
    },
    {
        path: 'top',
        name: 'user-top',
        component: () => import('./UserTopView.vue'),
    },
    {
        path: 'pb',
        name: 'user-pb',
        component: () => import('./UserPBView.vue'),
    },
    {
        path: 'videos',
        name: 'user-videos',
        component: () => import('./UserVideoView.vue'),
    },
    {
        path: 'medals',
        name: 'user-medals',
        component: () => import('./UserMedalView.vue'),
    },
    {
        path: 'upload',
        name: 'user-upload',
        component: () => import('./UserUploadView.vue'),
    },
];
