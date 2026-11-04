<template>
    <ElTabPane v-loading="loading" class="home-news-pane" name="news">
        <template #label>
            {{ globalI18n.t('home.news') }}&nbsp;
            <BaseTextButton
                underline="never" :disabled="loading" :aria-label="t('local.refresh')"
                style="vertical-align: baseline;" @keydown.stop @click="refresh"
            >
                <BaseIconRefresh />
            </BaseTextButton>
        </template>
        <div class="news-categories">
            <button
                v-for="item in categories" :key="item.value" type="button"
                class="news-category" :class="{ 'is-active': category === item.value }"
                @click="select(item.value)"
            >
                {{ t(item.label) }}
            </button>
        </div>
        <div v-if="!events.length" class="news-empty">
            {{ t('local.empty') }}
        </div>
        <ul v-else class="news-list">
            <li v-for="event in events" :key="event.id" class="news-item" :data-cy="`news-${event.category}`">
                <span class="news-time">{{ formatTime(event.occurred_at) }}</span>
                <PlayerName class="news-player" :user-id="event.player_id" />
                <span class="news-text">{{ describe(event) }}</span>
                <span class="news-replays">
                    <template v-for="(id, index) in replayIds(event)" :key="id">
                        <span v-if="index" class="news-arrow"> → </span>
                        <a :href="`#/video/${id}`">#{{ id }}</a>
                    </template>
                </span>
            </li>
        </ul>
    </ElTabPane>
</template>

<script setup lang='ts'>
import { ElTabPane, vLoading } from 'element-plus';
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { BaseIconRefresh } from '@/components/common/icon';
import PlayerName from '@/components/PlayerName.vue';
import { fetchNews } from '@/services/newsService';
import type { NewsCategory, NewsEvent } from '@/services/newsService';
import { utc_to_local_format } from '@/utils/system/tools';

const globalI18n = useI18n({ useScope: 'global' });

const categories: { value: NewsCategory; label: string }[] = [
    { value: 'all', label: 'local.all' },
    { value: 'pb', label: 'local.pb' },
    { value: 'lsf', label: 'local.lsf' },
];

const category = ref<NewsCategory>('all');
const events = ref<NewsEvent[]>([]);
const loading = ref(false);

onMounted(refresh);

async function select(value: NewsCategory) {
    if (category.value === value) return;
    category.value = value;
    await refresh();
}

async function refresh() {
    loading.value = true;
    try {
        events.value = await fetchNews(category.value);
    } catch {
        events.value = [];
    } finally {
        loading.value = false;
    }
}

function formatTime(timestamp: number): string {
    return utc_to_local_format(new Date(timestamp).toISOString());
}

function formatTimeValue(timems: number): string {
    return (timems / 1000).toFixed(3);
}

function formatRank(rank: number | null): string {
    return rank === null ? '--' : String(rank);
}

function formatField(field: string): string {
    const [mode, level, bv] = field.split(':');
    return `${mode.toUpperCase()} ${level.toUpperCase()} BV${bv}`;
}

function replayIds(event: NewsEvent): number[] {
    if (event.category === 'pb') {
        return [event.payload.old?.video_id, event.payload.new.video_id].filter((id): id is number => id != null);
    }
    return event.payload.video_ids ?? (event.payload.video_id == null ? [] : [event.payload.video_id]);
}

function describe(event: NewsEvent): string {
    if (event.category === 'pb') {
        const { field, old, new: current } = event.payload;
        if (!old) {
            return t('local.pbFirst', { field: formatField(field), newTime: formatTimeValue(current.timems), newRank: formatRank(current.rank) });
        }
        return t('local.pbImproved', {
            field: formatField(field),
            oldTime: formatTimeValue(old.timems),
            newTime: formatTimeValue(current.timems),
            oldRank: formatRank(old.rank),
            newRank: formatRank(current.rank),
        });
    }
    const { old, new: current } = event.payload;
    if (!old) {
        return t('local.lsfFirst', { newLsf: current.lsf.toFixed(2), newRank: formatRank(current.rank) });
    }
    return t('local.lsfImproved', {
        oldLsf: old.lsf.toFixed(2),
        newLsf: current.lsf.toFixed(2),
        oldRank: formatRank(old.rank),
        newRank: formatRank(current.rank),
    });
}

const i18nMessages = {
    'zh-cn': { local: {
        all: '全部',
        pb: 'PB榜',
        lsf: 'LSF',
        empty: '暂无新闻',
        refresh: '刷新',
        pbImproved: '将{field}的PB从{oldTime}刷新为{newTime}，排名{oldRank} → {newRank}',
        pbFirst: '首次进入{field}榜第{newRank}名，成绩{newTime}',
        lsfImproved: 'LSF从{oldLsf}提升至{newLsf}，排名{oldRank} → {newRank}',
        lsfFirst: '首次进入LSF榜第{newRank}名，LSF {newLsf}',
    } },
    en: { local: {
        all: 'All',
        pb: 'PB',
        lsf: 'LSF',
        empty: 'No news yet',
        refresh: 'Refresh',
        pbImproved: 'improved their {field} PB from {oldTime} to {newTime}, rank {oldRank} → {newRank}',
        pbFirst: 'entered the {field} board at #{newRank} with {newTime}',
        lsfImproved: 'LSF rose from {oldLsf} to {newLsf}, rank {oldRank} → {newRank}',
        lsfFirst: 'entered the LSF board at #{newRank} with {newLsf}',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.news-categories {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
}

.news-category {
    background: transparent;
    border: 1px solid var(--ui-border-color-lighter, #dcdfe6);
    border-radius: 4px;
    color: inherit;
    cursor: pointer;
    font-size: 13px;
    padding: 2px 10px;
}

.news-category.is-active {
    background: var(--ui-fill-color-light, #f5f7fa);
    border-color: var(--ui-color-primary, #409eff);
    color: var(--ui-color-primary, #409eff);
}

.news-empty {
    display: grid;
    min-height: 200px;
    place-items: center;
}

.news-list {
    list-style: none;
    margin: 0;
    max-height: 240px;
    overflow: auto;
    padding: 0;
}

.news-item {
    align-items: baseline;
    border-bottom: 1px solid var(--ui-border-color-lighter, #dcdfe6);
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 6px 0;
}

.news-time {
    color: var(--ui-text-color-secondary, #909399);
    font-size: 12px;
}

.news-text {
    flex: 1 1 240px;
}

.news-replays {
    font-size: 12px;
}

.news-arrow {
    color: var(--ui-text-color-secondary, #909399);
}
</style>
