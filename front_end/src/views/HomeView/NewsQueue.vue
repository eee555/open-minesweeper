<template>
    <ElTabPane class="home-news-pane" :label="label" :name="category" lazy>
        <div v-loading="loading" class="news-body">
            <div v-if="!loading && !events.length" class="news-empty text-secondary">
                {{ t('local.empty') }}
            </div>
            <ul v-else-if="events.length" class="news-list">
                <li v-for="event in events" :key="event.id" class="news-item" :data-cy="`news-${event.category}`">
                    <span class="news-time text-secondary text-small">{{ formatTime(event.occurred_at) }}</span>
                    <span class="news-sentence">
                        <template v-if="event.category === 'pb'"><PlayerName class="news-player" :user-id="event.player_id" />{{ pbPrefix(event) }}<template v-if="event.payload.old"><VideoPreviewLink :id="event.payload.old.video_id">{{ formatTimeValue(event.payload.old.timems) }}</VideoPreviewLink>({{ formatRank(event.payload.old.rank) }}) → </template><VideoPreviewLink :id="event.payload.new.video_id">{{ formatTimeValue(event.payload.new.timems) }}</VideoPreviewLink>({{ formatRank(event.payload.new.rank) }})</template>
                        <template v-else-if="event.category === 'eff'"><PlayerName class="news-player" :user-id="event.player_id" />{{ effPrefix(event) }}<template v-if="event.payload.old"><VideoPreviewLink v-if="event.payload.old.video_id !== null" :id="event.payload.old.video_id">{{ formatEffValue(event.payload.old, event.payload.field) }}</VideoPreviewLink><template v-else>{{ formatEffValue(event.payload.old, event.payload.field) }}</template>({{ formatRank(event.payload.old.rank) }}) → </template><VideoPreviewLink v-if="event.payload.new.video_id !== null" :id="event.payload.new.video_id">{{ formatEffValue(event.payload.new, event.payload.field) }}</VideoPreviewLink><template v-else>{{ formatEffValue(event.payload.new, event.payload.field) }}</template>({{ formatRank(event.payload.new.rank) }})</template>
                        <template v-else-if="event.category === 'lsf'"><template v-for="(id, index) in lsfReplayIds(event)" :key="id">{{ index ? ' ' : '' }}<VideoPreviewLink :id="id">#{{ id }}</VideoPreviewLink></template>{{ t('local.lsfRaised') }}<PlayerName class="news-player" :user-id="event.player_id" />{{ lsfDescription(event) }}</template>
                    </span>
                </li>
            </ul>
        </div>
    </ElTabPane>
</template>

<script setup lang='ts'>
import { ElTabPane, vLoading } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import PlayerName from '@/components/PlayerName.vue';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import i18n from '@/i18n';
import { fetchNews, formatEffValue } from '@/services/newsService';
import type { NewsCategory, NewsEvent } from '@/services/newsService';
import { utc_to_local_format } from '@/utils/system/tools';

const props = defineProps({
    category: { type: String, default: 'all' },
    // 未传入时视为始终激活，保持组件独立使用与单组件测试的行为。
    isActive: { type: Boolean, default: true },
});
const category = computed(() => props.category as NewsCategory);

const events = ref<NewsEvent[]>([]);
const loading = ref(false);
const loaded = ref(false);

function ensureLoaded() {
    if (props.isActive && !loaded.value) void refresh();
}

onMounted(ensureLoaded);
watch(() => props.isActive, ensureLoaded);

async function refresh() {
    if (loading.value) return;
    loading.value = true;
    // 请求发出即标记，避免来回切换 tab 时重复请求；手动刷新不受此标记限制。
    loaded.value = true;
    try {
        events.value = await fetchNews(category.value);
    } catch {
        events.value = [];
    } finally {
        loading.value = false;
    }
}

// 刷新按钮位于父级 tab 头部右侧，只调用当前激活 tab 的 refresh。
defineExpose({ refresh });

function formatTime(timestamp: number): string {
    return utc_to_local_format(new Date(timestamp).toISOString());
}

function formatTimeValue(timems: number): string {
    return (timems / 1000).toFixed(3);
}

function formatLsfValue(lsf: number): string {
    return lsf.toFixed(2);
}

function formatRank(rank: number | null): string {
    return rank === null ? '--' : String(rank);
}

function formatField(field: string): string {
    const [mode, level, bv] = field.split(':');
    const levelName = i18n.global.t(`level.${level}`);
    const separator = i18n.global.locale.value.startsWith('zh') ? '' : ' ';
    // 中文示例「高级150NFPB」：NF 紧跟 BV 后直接接 PB；标准模式不标注，英文保持分词。
    const nf = mode === 'nf' ? `${separator}NF` : '';
    return `${levelName}${separator}${bv}${nf}`;
}

function formatEffField(field: string): string {
    const [ranking, stat] = field.split(':');
    const separator = i18n.global.locale.value.startsWith('zh') ? '' : ' ';
    const rankingName = ranking === 'thrp' ? i18n.global.t('prop.thrp') : t('local.nfIOE');
    let statName = i18n.global.t(`level.${stat}`);
    if (stat === 'sum') statName = i18n.global.t('level.sum');
    if (stat === 'e_nf') statName = `${i18n.global.t('level.e')}${separator}${i18n.global.t('nf')}`;
    return `${rankingName}${separator}${statName}`;
}

function effPrefix(event: NewsEvent): string {
    if (event.category !== 'eff') return '';
    const field = formatEffField(event.payload.field);
    return event.payload.old ? t('local.effImproved', { field }) : t('local.effFirst', { field });
}

// PB 与效率新闻以玩家为主语，前后两个成绩数字各自链接到对应录像；LSF 以录像为主语，句首列出全部相关录像。
function pbPrefix(event: NewsEvent): string {
    if (event.category !== 'pb') return '';
    const field = formatField(event.payload.field);
    return event.payload.old ? t('local.pbImproved', { field }) : t('local.pbFirst', { field });
}

function lsfReplayIds(event: NewsEvent): number[] {
    if (event.category !== 'lsf') return [];
    return event.payload.video_ids ?? (event.payload.video_id == null ? [] : [event.payload.video_id]);
}

function lsfDescription(event: NewsEvent): string {
    if (event.category !== 'lsf') return '';
    const { old, new: current } = event.payload;
    if (!old) {
        return t('local.lsfFirstOfPlayer', { newLsf: formatLsfValue(current.lsf), newRank: formatRank(current.rank) });
    }
    return t('local.lsfOfPlayer', {
        oldLsf: formatLsfValue(old.lsf),
        newLsf: formatLsfValue(current.lsf),
        oldRank: formatRank(old.rank),
        newRank: formatRank(current.rank),
    });
}

const i18nMessages = {
    'zh-cn': { local: {
        news: '新闻',
        pb: 'PB榜',
        lsf: 'LSF',
        eff: '效率',
        nfIOE: 'NF IOE',
        empty: '暂无新闻',
        pbImproved: '打破了{field}PB：',
        pbFirst: '首次取得{field}PB：',
        effImproved: '打破了{field}纪录：',
        effFirst: '首次取得{field}纪录：',
        lsfRaised: '提升了',
        lsfOfPlayer: '的LSF：{oldLsf}({oldRank}) → {newLsf}({newRank})',
        lsfFirstOfPlayer: '的LSF首次上榜：{newLsf}({newRank})',
    } },
    en: { local: {
        news: 'News',
        pb: 'PB',
        lsf: 'LSF',
        eff: 'Eff',
        nfIOE: 'NF IOE',
        empty: 'No news yet',
        pbImproved: ' broke the {field} PB: ',
        pbFirst: ' set their first {field} PB: ',
        effImproved: ' broke the {field} record: ',
        effFirst: ' set their first {field} record: ',
        lsfRaised: ' raised ',
        lsfOfPlayer: '\'s LSF: {oldLsf}({oldRank}) → {newLsf}({newRank})',
        lsfFirstOfPlayer: '\'s LSF entered the board: {newLsf}({newRank})',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
const label = computed(() => {
    const c = category.value;
    return c === 'pb' ? t('local.pb') : c === 'lsf' ? t('local.lsf') : c === 'eff' ? t('local.eff') : t('local.news');
});
</script>

<style scoped>
.news-body {
    min-width: 0;
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
    border-bottom: 1px solid var(--ui-border-color-lighter);
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 4px 0;
}

.news-sentence {
    flex: 1 1 240px;
    line-height: 1.6;
    min-width: 0;
    overflow-wrap: anywhere;
}
</style>
