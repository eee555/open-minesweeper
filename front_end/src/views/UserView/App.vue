<template>
    <div ref="containerRef" v-loading="playerLoading" class="personal-homepage" :class="{ 'wide-mode': isWide, 'narrow-mode': !isWide }">
        <div class="profile-section">
            <Profile :user="store.player" :direction="isWide ? 'vertical' : 'horizontal'" />
        </div>
        <div class="content-area">
            <ElTabs :model-value="activeTab" data-cy="profile-tabs" @tab-click="handleTabClick">
                <ElTabPane v-for="tab in tabItems" :key="tab.name" :label="tab.label" :name="tab.name" />
                <router-view v-slot="{ Component }">
                    <keep-alive>
                        <component :is="Component" v-model:user="store.player" />
                    </keep-alive>
                </router-view>
            </ElTabs>
        </div>
    </div>
</template>

<script lang="ts" setup>
import { useElementSize } from '@vueuse/core';
import type { TabsPaneContext } from 'element-plus';
import { ElTabPane, ElTabs, vLoading } from 'element-plus';
import { computed, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import Profile from './Profile.vue';
import { usePlayer } from './usePlayer';

import { store } from '@/store';

const route = useRoute();
const router = useRouter();

const tabItems = computed(() => {
    const ret = [
        { name: 'top', label: 'Top' },
        { name: 'pb', label: 'PB' },
        { name: 'record', label: t('local.record') },
        { name: 'accountlink', label: t('local.accountlink') },
        { name: 'videos', label: t('local.videos') },
    ];
    if (store.isSelf) {
        ret.push({ name: 'upload', label: t('common.button.upload') });
        ret.push({ name: 'settings', label: t('common.settings') });
    }
    return ret;
});
const validTabs = computed(() => tabItems.value.map((item) => item.name));

const activeTab = computed(() => {
    const lastSegment = route.path.split('/').pop() ?? '';
    return validTabs.value.includes(lastSegment) ? lastSegment : 'top';
});

const handleTabClick = (tab: TabsPaneContext) => {
    const tabName = tab.paneName;
    if (tabName !== undefined) void router.replace(String(tabName));
};

const playerLoading = usePlayer(() => Number(Array.isArray(route.params.id) ? route.params.id[0] : route.params.id));

const containerRef = useTemplateRef('containerRef');
const { width } = useElementSize(containerRef);
const isWide = computed(() => width.value >= 960);

const i18nMessages = {
    'zh-cn': { local: {
        accountlink: '账号关联',
        record: '纪录',
        videos: '录像',
    } },
    en: { local: {
        accountlink: 'Account Link',
        record: 'Record',
        videos: 'Videos',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped lang="less">
.personal-homepage {
    display: flex;

    &.narrow-mode {
        flex-direction: column;
        .profile-section { width: 100%; }
        .content-area {
            width: 100%;
            margin-top: 1rem;
        }
    }

    &.wide-mode {
        flex-direction: row;
        .profile-section {
            width: 200px;
            min-width: 200px;
        }
        .content-area {
            flex: 1;
            margin-left: 1rem;
            overflow-y: auto;
        }
    }
}
</style>
