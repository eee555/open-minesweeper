import type { RouteRecordRaw } from 'vue-router';

// 每项资源一个独立路径，全部渲染同一个 ResourcesView，标签由当前路径决定。
const resourceIds = ['metasweeper', 'arbiter', 'vienna', 'classic95', 'analyzer', 'yuanshen'] as const;
const firstResourcePath = `/resources/${resourceIds[0]}`;

export const resourceRoutes: RouteRecordRaw[] = [
    ...resourceIds.map((id) => ({
        path: `/resources/${id}`,
        name: `resources-${id}`,
        component: () => import('./App.vue'),
    })),
    // 未知子路径回到第一项，避免空白页。
    { path: '/resources/:tab', redirect: firstResourcePath },
];
