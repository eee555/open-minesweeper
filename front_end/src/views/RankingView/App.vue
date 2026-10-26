<template>
    <ElTabs :model-value="activeTab" @tab-click="handleTabClick">
        <ElTabPane v-for="tab in tabItems" :key="tab.name" :label="tab.label" :name="tab.name" />
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

const route = useRoute();
const router = useRouter();

const handleTabClick = (tab: TabsPaneContext) => {
    const tabName = tab.paneName;
    if (tabName === activeTab.value) return;
    if (tabName !== undefined) void router.replace({ name: `ranking_${String(tabName)}` });
};

const i18nMessages = {
    'zh-cn': { local: {
        speed: '竞速',
        efficiency: '效率',
        density: '密度',
    } },
    en: { local: {
        speed: 'Speed',
        efficiency: 'Efficiency',
        density: 'Density',
    } },
};

const { t } = useI18n({ messages: i18nMessages });

const tabItems = computed(() => [
    { name: 'speed', label: t('local.speed') },
    { name: 'efficiency', label: t('local.efficiency') },
    { name: 'density', label: t('local.density') },
    { name: 'tournament', label: t('tournament.tournament') },
    { name: 'minigame', label: t('minigame.title') },
]);
const activeTab = computed(() => {
    return tabItems.value.find((tab) => route.matched.some((record) => record.name === `ranking_${tab.name}`))?.name ?? 'speed';
});
</script>
