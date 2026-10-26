<template>
    <ElTabs :model-value="activeTab" @tab-click="handleTabClick">
        <ElTabPane :label="t('local.users')" name="users" />
        <ElTabPane :label="t('local.videos')" name="videos" />
        <ElTabPane :label="t('local.identifiers')" name="identifiers" />
    </ElTabs>
    <router-view v-slot="{ Component }">
        <keep-alive>
            <component :is="Component" />
        </keep-alive>
    </router-view>
</template>

<script setup lang="ts">
import type { TabsPaneContext } from 'element-plus';
import { ElTabPane, ElTabs } from 'element-plus';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();
const activeTab = computed(() => {
    if (route.name === 'database-videos') return 'videos';
    if (route.name === 'database-identifiers') return 'identifiers';
    return 'users';
});

function handleTabClick(tab: TabsPaneContext) {
    if (tab.paneName !== undefined) void router.replace({ name: `database-${String(tab.paneName)}` });
}

const i18nMessages = {
    'zh-cn': { local: { users: '用户', videos: '录像', identifiers: '标识查询' } },
    en: { local: { users: 'Users', videos: 'Videos', identifiers: 'Identifier Lookup' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
