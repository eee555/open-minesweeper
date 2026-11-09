<template>
    <div class="works-tabs-wrapper">
        <ElTabs :model-value="activeTab" class="works-tabs" @tab-click="handleTabClick">
            <ElTabPane :label="t('media.hot')" name="hot" />
            <ElTabPane :label="t('media.likes')" name="likes" />
            <ElTabPane :label="t('media.latest')" name="latest" />
            <ElTabPane :label="t('media.pending')" name="pending" />
        </ElTabs>
        <div class="works-tabs-actions">
            <BaseButton size="small" type="primary" data-cy="open-submit" @click="dialogOpen = true">
                {{ t('local.submit') }}
            </BaseButton>
            <BaseButton
                size="small" class="square-button" :title="t('local.refresh')"
                :aria-label="t('local.refresh')" data-cy="refresh-works" @click="refreshCurrentTab"
            >
                <template #icon>
                    <BaseIconRefresh />
                </template>
            </BaseButton>
        </div>
    </div>
    <router-view v-slot="{ Component }">
        <keep-alive>
            <component :is="Component" ref="activeView" />
        </keep-alive>
    </router-view>
    <SubmitMediaDialog v-if="dialogOpen" @close="dialogOpen = false" @submitted="onSubmitted" />
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus-tabs.less';
import type { TabsPaneContext } from 'element-plus';
import { ElNotification, ElTabPane, ElTabs } from 'element-plus';
import { computed, ref, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import BaseButton from '@/components/common/BaseButton.vue';
import { BaseIconRefresh } from '@/components/common/icon';
import SubmitMediaDialog from '@/components/media/SubmitMediaDialog.vue';
import type { MediaItem } from '@/services/mediaService';

const route = useRoute();
const router = useRouter();

const activeTab = computed(() => {
    if (route.name === 'works-likes') return 'likes';
    if (route.name === 'works-latest') return 'latest';
    if (route.name === 'works-pending') return 'pending';
    return 'hot';
});

const activeView = useTemplateRef<{ refresh?: () => void }>('activeView');
const dialogOpen = ref(false);

function handleTabClick(tab: TabsPaneContext) {
    if (tab.paneName !== undefined) void router.replace({ name: `works-${String(tab.paneName)}` });
}

function refreshCurrentTab(): void {
    activeView.value?.refresh?.();
}

function onSubmitted(media: MediaItem): void {
    dialogOpen.value = false;
    ElNotification({
        title: t('local.submitDone'),
        message: media.metadata_pending ? t('local.degradedHint') : t('local.normalHint'),
        type: 'success',
    });
    if (media.metadata_pending) void router.replace({ name: 'works-pending' });
    refreshCurrentTab();
}

const i18nMessages = {
    'zh-cn': { local: {
        submit: '投稿',
        refresh: '刷新',
        submitDone: '投稿成功',
        normalHint: '作品已进入审核队列',
        degradedHint: '投稿已保留，标题由管理员审核时补全并核验外站账号',
    } },
    en: { local: {
        submit: 'Submit',
        refresh: 'Refresh',
        submitDone: 'Submitted',
        normalHint: 'Your work is now in the review queue',
        degradedHint: 'Submission kept; a moderator will fill in the title and verify the external account',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped lang="css">
.works-tabs-wrapper {
    min-width: 0;
    position: relative;
}

/* 给 header 右侧的投稿与刷新按钮留出空间，避免与 tab 项重叠。 */
.works-tabs :deep(.el-tabs__header) {
    padding-inline-end: 160px;
}

.works-tabs-actions {
    align-items: center;
    display: flex;
    gap: 4px;
    height: 40px;
    position: absolute;
    right: 8px;
    top: 0;
    z-index: 1;
}
</style>
