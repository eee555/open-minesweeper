<template>
    <ElTabs :model-value="activeTab" @tab-click="handleTabClick">
        <ElTabPane :label="t('media.hot')" name="hot" />
        <ElTabPane :label="t('media.likes')" name="likes" />
        <ElTabPane :label="t('media.latest')" name="latest" />
        <ElTabPane :label="t('media.pending')" name="pending" />
    </ElTabs>
    <router-view v-slot="{ Component }">
        <keep-alive>
            <component :is="Component" />
        </keep-alive>
    </router-view>
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus-tabs.less';
import type { TabsPaneContext } from 'element-plus';
import { ElTabPane, ElTabs } from 'element-plus';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();
const { t } = useI18n();

const activeTab = computed(() => {
    if (route.name === 'works-likes') return 'likes';
    if (route.name === 'works-latest') return 'latest';
    if (route.name === 'works-pending') return 'pending';
    return 'hot';
});

function handleTabClick(tab: TabsPaneContext) {
    if (tab.paneName !== undefined) void router.replace({ name: `works-${String(tab.paneName)}` });
}
</script>
