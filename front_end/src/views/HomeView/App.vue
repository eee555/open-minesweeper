<template>
    <div class="home-content">
        <div class="home-top-row">
            <div class="home-news-tabs-wrapper">
                <ElTabs v-model="active_news_tab" class="home-news-tabs" type="border-card">
                    <NewsQueue ref="newsAll" category="all" :is-active="active_news_tab === 'all'" />
                    <NewsQueue ref="newsPb" category="pb" :is-active="active_news_tab === 'pb'" />
                    <NewsQueue ref="newsLsf" category="lsf" :is-active="active_news_tab === 'lsf'" />
                </ElTabs>
                <BaseTextButton
                    class="home-news-refresh" size="small" underline="never"
                    :disabled="refreshing" :aria-label="t('local.refresh')" @click="refreshCurrentTab"
                >
                    <BaseIconRefresh />
                    <span>{{ t('local.refresh') }}</span>
                </BaseTextButton>
            </div>
            <NormalTournamentQueue />
        </div>
        <ElTabs v-model="active_tab" type="border-card" style="margin-top: 2%;">
            <NewestQueue :is-active="active_tab === 'newest'" />
            <ReviewQueue />
        </ElTabs>
    </div>
</template>

<script setup lang='ts'>
import { ElTabs } from 'element-plus';
import { ref, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';

import NewestQueue from './NewestQueue.vue';
import NewsQueue from './NewsQueue.vue';
import NormalTournamentQueue from './NormalTournamentQueue.vue';
import ReviewQueue from './ReviewQueue.vue';

import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { BaseIconRefresh } from '@/components/common/icon';

interface NewsQueueHandle {
    refresh: () => Promise<void>;
}

const active_tab = ref('newest');
const active_news_tab = ref('all');

const newsAll = useTemplateRef<NewsQueueHandle>('newsAll');
const newsPb = useTemplateRef<NewsQueueHandle>('newsPb');
const newsLsf = useTemplateRef<NewsQueueHandle>('newsLsf');
const refreshing = ref(false);

function currentQueue(): NewsQueueHandle | null {
    if (active_news_tab.value === 'pb') return newsPb.value;
    if (active_news_tab.value === 'lsf') return newsLsf.value;
    return newsAll.value;
}

async function refreshCurrentTab() {
    if (refreshing.value) return;
    refreshing.value = true;
    try {
        await currentQueue()?.refresh();
    } finally {
        refreshing.value = false;
    }
}

const i18nMessages = {
    'zh-cn': { local: { refresh: '刷新' } },
    en: { local: { refresh: 'Refresh' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style lang='less'>
.home-content {
    box-sizing: border-box;
    container-type: inline-size;
    min-width: 0;
    overflow: auto;
    padding: 1%;
}

.bottom_tabs {
    overflow: auto;
}

.aside-tip-title {
    font-size: 14px;
    display: flex;
    align-items: center;
    margin-top: 5%;
}

.text-button:hover {
    cursor: pointer;
}

.home-top-row {
    align-items: stretch;
    display: grid;
    gap: 2%;
    grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
}

.home-news-tabs-wrapper {
    display: grid;
    min-width: 0;
    position: relative;
}

.home-news-tabs {
    min-height: 300px;
    min-width: 0;
}

/* 给 header 右侧的刷新按钮留出空间，避免与 tab 项重叠。 */
.home-news-tabs > .el-tabs__header {
    padding-inline-end: 96px;
}

.home-news-refresh {
    align-items: center;
    display: inline-flex;
    height: 40px;
    position: absolute;
    right: 8px;
    top: 0;
    z-index: 1;
}

@container (max-width: 900px) {
    .home-top-row {
        grid-template-columns: 1fr;
    }
}
</style>
