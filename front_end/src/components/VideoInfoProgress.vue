<template>
    <div v-if="progress.total > progress.completed" class="text-small video-info-progress" role="status">
        <span>{{ t('local.progress', progress) }}</span>
        <progress :value="progress.completed" :max="progress.total" :aria-label="t('local.title')" />
    </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import { videoInfoDownloads } from '@/services/videoInfoService';

const route = useRoute();
const progress = computed(() => {
    const items = new Map<string, boolean>();
    for (const task of videoInfoDownloads.value) {
        if (task.page !== route.fullPath.split('#')[0]) continue;
        for (const [key, done] of task.items) items.set(key, (items.get(key) ?? true) && done);
    }
    return { total: items.size, completed: [...items.values()].filter(Boolean).length };
});

const i18nMessages = {
    'zh-cn': { local: {
        title: '录像信息下载进度',
        progress: '正在后台获取录像信息：{completed} / {total}',
    } },
    en: { local: {
        title: 'Video information download progress',
        progress: 'Loading video information in the background: {completed} / {total}',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-info-progress {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 12px;
    margin-bottom: 8px;
    padding: 4px 0;
    color: var(--ui-text-color-secondary);
}

.video-info-progress progress {
    flex: 0 1 16rem;
    width: 100%;
    min-width: 0;
    height: 8px;
    accent-color: var(--ui-color-primary);
}
</style>
