import type { RouteRecordRaw } from 'vue-router';

export const worksRoutes: RouteRecordRaw[] = [
    { path: 'hot', name: 'works-hot', component: () => import('./HotView.vue') },
    { path: 'likes', name: 'works-likes', component: () => import('./LikesView.vue') },
    { path: 'latest', name: 'works-latest', component: () => import('./LatestView.vue') },
    { path: 'pending', name: 'works-pending', component: () => import('./PendingView.vue') },
];
