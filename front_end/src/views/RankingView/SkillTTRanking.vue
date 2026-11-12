<template>
    <section class="skill-tt-ranking">
        <div class="derived-toolbar">
            <div class="button-group button-group--joined" role="group" :aria-label="t('local.views')" data-cy="derived-view">
                <BaseButton v-for="option in derivedPages" :key="option" size="small" :type="view === option ? 'primary' : 'default'" :aria-pressed="view === option" :data-view="option" @click="selectView(option)">
                    {{ viewLabel(option) }}
                </BaseButton>
            </div>
            <label class="checkbox nf-toggle">
                <input v-model="nf" class="checkbox-input" type="checkbox" data-cy="derived-nf">
                <span>{{ t('nf') }}</span>
            </label>
        </div>
        <p v-if="failed" role="alert" class="text-danger">
            {{ t('ranking.loadFailed') }}
        </p>
        <PBDerivedRankingTable :rows="rows" :columns="columns" :first="first" :sort="effectiveSort" :loading="loading" :colored="colored" @select-sort="selectSort" />
        <div class="derived-pagination">
            <ElPagination v-model:current-page="page" v-model:page-size="pageSize" layout="total, sizes, prev, pager, next, jumper" :page-sizes="[20, 50, 100]" :total="total" />
        </div>
    </section>
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus-select.css';
import { ElPagination } from 'element-plus';
import { computed, onScopeDispose, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import PBDerivedRankingTable from './PBDerivedRankingTable.vue';
import { queryChoice, queryInteger, queryNF, useRankingQuery } from './useRankingQuery';

import BaseButton from '@/components/common/BaseButton.vue';
import type { DerivedColumn, DerivedLevel, DerivedPage, DerivedRankingName, DerivedRankingRow } from '@/services/pbDerivedService';
import { defaultDerivedSort, derivedField, derivedOverviewKeys, derivedPages, derivedSegments, derivedSkillTTSortKeys, derivedSort, fetchDerivedRanking, modeKey, parseDerivedSort } from '@/services/pbDerivedService';
import type { MS_Level } from '@/utils/ms_const';

defineProps({ colored: { type: Boolean, default: false } });

const i18nMessages = {
    'zh-cn': { local: {
        views: '子页',
    } },
    en: { local: {
        views: 'Views',
    } },
};
const { t } = useI18n({ messages: i18nMessages });

const { fields: { view, sort, nf, page, page_size: pageSize }, update } = useRankingQuery<{ view: DerivedPage; sort: string; nf: boolean; page: number; page_size: number }>(
    { view: 'overview', sort: defaultDerivedSort('overview'), nf: false, page: 1, page_size: 20 },
    (query, defaults) => ({ view: queryChoice(query.view, derivedPages, defaults.view), sort: queryChoice(query.sort, derivedSkillTTSortKeys, defaults.sort), nf: queryNF(query.nf), page: queryInteger(query.page, defaults.page), page_size: queryChoice(query.page_size, [20, 50, 100], defaults.page_size) }),
    ['view', 'sort', 'nf', 'page_size'],
);
const first = computed(() => (page.value - 1) * pageSize.value);
const rows = ref<DerivedRankingRow[]>([]);
const total = ref(0);
const loading = ref(false);
const failed = ref(false);
let controller: AbortController | undefined;
let requestId = 0;

function viewLabel(option: DerivedPage): string {
    if (option === 'overview') return t('derived.overview');
    const [kind, level] = option.split('_');
    return `${t(`level.${level}`)} ${t(kind === 'skill' ? 'derived.skill' : 'derived.typicalTime')}`;
}

function overviewColumns(): DerivedColumn[] {
    const mode = modeKey(nf.value);
    return derivedOverviewKeys.map((key) => {
        const [rankingName, levelName, stat] = key.split(':');
        const ranking = rankingName as DerivedRankingName;
        const level = levelName as DerivedLevel;
        return {
            ranking,
            field: derivedField(mode, `${level}:${stat}`),
            sort: derivedSort(ranking, `${level}:${stat}`),
            metric: ranking === 'skill' ? 'skill' : 'tt',
            level,
            label: level === 'sum' ? t('derived.total') : t(`level.${level}`),
            group: t(ranking === 'skill' ? 'derived.skill' : 'derived.tt'),
            color: ranking === 'skill' ? level === 'sum' ? 'bvs-third' : 'bvs' : 'none',
        };
    });
}

function segmentColumns(): DerivedColumn[] {
    const [kind, levelName] = view.value.split('_');
    const ranking: DerivedRankingName = kind === 'skill' ? 'skill' : 'typical_time';
    const level = levelName as MS_Level;
    const mode = modeKey(nf.value);
    const metric = kind === 'skill' ? 'skill' : 'tt';
    const columns: DerivedColumn[] = derivedSegments[level].map((segment) => ({
        ranking,
        field: derivedField(mode, `${level}:${segment.field}`),
        sort: derivedSort(ranking, `${level}:${segment.field}`),
        metric,
        level,
        label: `${segment.start}–${segment.end}`,
        color: kind === 'skill' ? 'bvs' : 'time',
    }));
    columns.push({
        ranking,
        field: derivedField(mode, `${level}:total`),
        sort: derivedSort(ranking, `${level}:total`),
        metric,
        level,
        label: t('derived.total'),
        color: kind === 'skill' ? 'bvs' : 'none',
    });
    return columns;
}

const columns = computed<DerivedColumn[]>(() => {
    if (view.value === 'overview') return overviewColumns();
    return segmentColumns();
});
const effectiveSort = computed(() => {
    const allowed = columns.value.map((column) => column.sort);
    return allowed.includes(sort.value) ? sort.value : defaultDerivedSort(view.value);
});

function selectView(option: DerivedPage): void {
    void update({ view: option, sort: defaultDerivedSort(option) });
}

function selectSort(value: string): void {
    void update({ sort: value });
}

async function load(): Promise<void> {
    controller?.abort();
    controller = new AbortController();
    const { signal } = controller;
    const request = ++requestId;
    loading.value = true;
    failed.value = false;
    try {
        const { ranking, field } = parseDerivedSort(effectiveSort.value, nf.value);
        const data = await fetchDerivedRanking(ranking, field, first.value, first.value + pageSize.value, signal);
        if (request !== requestId || signal.aborted) return;
        rows.value = data.rows;
        total.value = data.count;
        if (first.value > 0 && first.value >= total.value) void update({ page: Math.max(1, Math.ceil(total.value / pageSize.value)) }, true);
    } catch {
        if (request !== requestId || signal.aborted) return;
        rows.value = [];
        total.value = 0;
        failed.value = true;
    } finally {
        if (request === requestId) loading.value = false;
    }
}

watch([view, sort, effectiveSort, nf, pageSize, page], () => {
    rows.value = [];
    void load();
}, { immediate: true });
onScopeDispose(() => {
    requestId++;
    controller?.abort();
});

defineExpose({ refresh: load, loading });
</script>

<style scoped>
.skill-tt-ranking {
    min-width: 0;
}
.derived-toolbar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 8px;
}
.derived-pagination {
    margin-top: 8px;
    overflow-x: auto;
}
.derived-pagination > :deep(.el-pagination) {
    width: max-content;
    margin-inline: auto;
}
</style>
