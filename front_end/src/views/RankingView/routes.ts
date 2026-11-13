import type { RouteRecordRaw } from 'vue-router';

import { trainingGames } from '@/utils/minigame/games';

export const rankingRoutes: RouteRecordRaw[] = [
    {
        path: 'speed',
        name: 'ranking_speed',
        component: () => import('./SpeedRanking.vue'),
        redirect: { name: 'ranking_speed_lsf' },
        children: [
            { path: 'lsf', name: 'ranking_speed_lsf', component: () => import('./LSFRanking.vue') },
            { path: 'top', name: 'ranking_speed_top', component: () => import('./TopRanking.vue') },
            { path: 'saolei', name: 'ranking_speed_saolei', component: () => import('./SaoleiRanking.vue') },
            { path: 'strict_ng', name: 'ranking_speed_strict_ng', component: () => import('./StrictNgRanking.vue') },
            { path: 'pb', name: 'ranking_speed_pb', component: () => import('./PBRanking.vue') },
            { path: 'collection', name: 'ranking_speed_collection', component: () => import('./CollectionRanking.vue') },
            { path: 'skill_tt', name: 'ranking_speed_skill_tt', component: () => import('./SkillTTRanking.vue') },
        ],
    },
    {
        path: 'efficiency',
        name: 'ranking_efficiency',
        component: () => import('./EfficiencyRanking.vue'),
        redirect: { name: 'ranking_efficiency_thrp' },
        children: [
            { path: 'thrp', name: 'ranking_efficiency_thrp', component: () => import('./ThrpRanking.vue') },
            { path: 'nf-ioe', name: 'ranking_efficiency_nf_ioe', component: () => import('./NFIOERanking.vue') },
        ],
    },
    {
        path: 'minigame',
        name: 'ranking_minigame',
        component: () => import('./MinigameRanking.vue'),
        redirect: { name: 'ranking_minigame_left-click' },
        children: trainingGames.map((game) => ({
            path: game,
            name: `ranking_minigame_${game}`,
            component: () => import('./MinigameRankingTable.vue'),
            props: { game },
        })),
    },
    {
        path: 'density',
        name: 'ranking_density',
        component: () => import('./DensityRanking.vue'),
    },
    {
        path: 'tournament',
        name: 'ranking_tournament',
        component: () => import('./TournamentRanking.vue'),
    },
    {
        path: 'media',
        name: 'ranking_media',
        component: () => import('./MediaRanking.vue'),
    },
];
