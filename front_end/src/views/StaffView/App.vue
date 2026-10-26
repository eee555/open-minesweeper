<template>
    <ElTabs :model-value="activeTab" @tab-click="handleTabClick">
        <ElTabPane v-for="tab in visibleTabs" :key="tab.name" :label="t(`local.${tab.name}`)" :name="tab.name" />
        <router-view v-slot="{ Component }">
            <keep-alive>
                <component :is="Component" />
            </keep-alive>
        </router-view>
    </ElTabs>
</template>

<script lang="ts" setup>
import type { TabsPaneContext } from 'element-plus';
import { ElTabPane, ElTabs } from 'element-plus';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import { store } from '@/store';

const route = useRoute();
const router = useRouter();

const tabItems = [
    { name: 'userprofile' },
    { name: 'videomodel' },
    { name: 'accountlink' },
    { name: 'identifier' },
    { name: 'logs' },
    { name: 'tournament' },
    { name: 'weekly-tournament' },
    { name: 'task' },
    { name: 'batchvideo' },
    { name: 'batchpluck' },
    { name: 'ranking-repair' },
    { name: 'medals' },
] as const;
const validTabs = tabItems.map((item) => item.name);
const visibleTabs = computed(() => tabItems.filter((item) => item.name !== 'medals' || store.user.is_staff));

// 根据当前路由路径计算激活的选项卡 name
const activeTab = computed(() => {
    const lastSegment = route.path.split('/').pop() ?? '';
    return (validTabs as string[]).includes(lastSegment) ? lastSegment : 'userprofile';
});

// 点击选项卡时跳转到对应子路由
const handleTabClick = (tab: TabsPaneContext) => {
    const tabName = tab.paneName;
    if (tabName !== undefined) void router.replace(String(tabName));
};

const i18nMessages = {
    'zh-cn': { local: {
        medals: '勋章管理',
        userprofile: '用户信息',
        videomodel: '录像信息',
        accountlink: '账号绑定',
        identifier: '标识管理',
        logs: '后台日志',
        tournament: '比赛管理',
        'weekly-tournament': '创建打卡赛',
        task: '后台任务',
        batchvideo: '批量刷新录像',
        batchpluck: '批量刷新pLuck纪录',
        'ranking-repair': '排行纪录重建',
    } },
    en: { local: {
        medals: 'Medal management',
        userprofile: 'User profiles',
        videomodel: 'Video information',
        accountlink: 'Account links',
        identifier: 'Identifier management',
        logs: 'Server logs',
        tournament: 'Tournament management',
        'weekly-tournament': 'Create weekly tournament',
        task: 'Background tasks',
        batchvideo: 'Batch refresh videos',
        batchpluck: 'Batch refresh pLuck records',
        'ranking-repair': 'Rebuild ranking records',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
