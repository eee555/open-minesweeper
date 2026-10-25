import type { RouteRecordRaw } from 'vue-router';
import { createRouter, createWebHashHistory } from 'vue-router';

import { rankingRoutes } from '@/views/RankingView/routes';
import { staffRoutes } from '@/views/StaffView/routes';
import { userRoutes } from '@/views/UserView/routes';

const routes: RouteRecordRaw[] = [
    {
        path: '/',
        name: 'home',
        component: () => import('../views/HomeView/App.vue'),
    },
    {
        path: '/ranking',
        name: 'ranking',
        component: () => import('../views/RankingView/App.vue'),
        redirect: '/ranking/speed',
        children: rankingRoutes,
    },
    {
        path: '/video',
        name: 'video',
        redirect: { name: 'database-videos' },
    },
    {
        path: '/database',
        name: 'database',
        component: () => import('../views/DatabaseView/App.vue'),
        redirect: { name: 'database-videos' },
        children: [
            { path: 'videos', name: 'database-videos', component: () => import('../views/VideoView.vue') },
            { path: 'identifiers', name: 'database-identifiers', component: () => import('../views/DatabaseView/IdentifierView.vue') },
        ],
    },
    {
        path: '/video/:id',
        name: 'video_id',
        component: () => import('../views/VideoAnalyzerView/App.vue'),
        props: true,
    },
    {
        path: '/server',
        name: 'server',
        component: () => import('../views/ServerView/App.vue'),
    },
    {
        path: '/minigame',
        component: () => import('../views/MiniGameView/App.vue'),
        redirect: '/minigame/left-click',
        children: [
            { path: 'left-click', name: 'minigame-left-click', component: () => import('../views/MiniGameView/LeftClickTraining/App.vue') },
            { path: 'multi-touch', name: 'minigame-multi-touch', component: () => import('../views/MiniGameView/LeftClickTraining/App.vue'), props: { gameType: 'multi-touch' } },
            { path: 'flag-chord', name: 'minigame-flag-chord', component: () => import('../views/MiniGameView/FlagChordTraining/App.vue') },
            { path: 'missing-cell', name: 'minigame-missing-cell', component: () => import('../views/MiniGameView/MissingCellTraining/App.vue') },
        ],
    },
    {
        path: '/settings',
        name: 'settings',
        component: () => import('../views/SettingView/App.vue'),
    },
    {
        path: '/player/:id',
        name: 'player_id',
        component: () => import('../views/UserView/App.vue'),
        redirect: (to) => {
            const { id } = to.params;
            if (typeof id !== 'string') return '/player/0/top';

            return `/player/${id}/top`;
        },
        children: userRoutes,
    },
    {
        path: '/staff',
        name: 'staff',
        component: () => import('../views/StaffView/App.vue'),
        redirect: '/staff/userprofile',
        children: staffRoutes,
    },
    {
        path: '/superuser/delete-videos',
        name: 'superuser-delete-videos',
        component: () => import('../views/StaffView/DeleteVideos.vue'),
    },
    {
        path: '/tournament/:id',
        name: 'tournament_id',
        component: () => import('../views/TournamentView/TournamentView.vue'),
    },
    {
        path: '/tournament',
        name: 'tournament',
        component: () => import('../views/TournamentView/TournamentView.vue'),
    },
    {
        path: '/gsc/admin',
        name: 'gsc_admin',
        component: () => import('../views/GSCAdminView.vue'),
    },
];

const router = createRouter({
    history: createWebHashHistory(import.meta.env.BASE_URL),
    routes,
});

export default router;
