<template>
    <section class="collection-ranking">
        <div class="derived-toolbar">
            <label class="checkbox nf-toggle">
                <input v-model="nf" class="checkbox-input" type="checkbox" data-cy="derived-nf">
                <span>{{ t('nf') }}</span>
            </label>
        </div>
        <p v-if="failed" role="alert" class="text-danger">
            {{ t('ranking.loadFailed') }}
        </p>
        <PBDerivedRankingTable :rows="rows" :columns="columns" :first="first" :sort="sort" :loading="loading" :colored="colored" @select-sort="selectSort" />
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

import type { DerivedColumn, DerivedLevel, DerivedMetric, DerivedRankingRow } from '@/services/pbDerivedService';
import { derivedCollectionKeys, derivedField, derivedSort, fetchDerivedRanking, modeKey, parseDerivedSort } from '@/services/pbDerivedService';

defineProps({ colored: { type: Boolean, default: false } });

const collectionSorts = derivedCollectionKeys.map((key) => derivedSort('collection', key));
const { fields: { nf, sort, page, page_size: pageSize }, update } = useRankingQuery<{ nf: boolean; sort: string; page: number; page_size: number }>(
    { nf: false, sort: derivedSort('collection', 'sum:count'), page: 1, page_size: 20 },
    (query, defaults) => ({ nf: queryNF(query.nf), sort: queryChoice(query.sort, collectionSorts, defaults.sort), page: queryInteger(query.page, defaults.page), page_size: queryChoice(query.page_size, [20, 50, 100], defaults.page_size) }),
    ['nf', 'sort', 'page_size'],
);
const first = computed(() => (page.value - 1) * pageSize.value);
const rows = ref<DerivedRankingRow[]>([]);
const total = ref(0);
const loading = ref(false);
const failed = ref(false);
let controller: AbortController | undefined;
let requestId = 0;

const columns = computed<DerivedColumn[]>(() => derivedCollectionKeys.map((key) => {
    const [level, metric] = key.split(':');
    return {
        ranking: 'collection',
        field: derivedField(modeKey(nf.value), key),
        sort: derivedSort('collection', key),
        metric: metric as DerivedMetric,
        level: level as DerivedLevel,
        label: t(`derived.${metric}`),
        group: levelGroup(level),
        color: 'none',
    };
}));

function levelGroup(level: string): string {
    return level === 'sum' ? t('derived.total') : t(`level.${level}`);
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
        const { ranking, field } = parseDerivedSort(sort.value, nf.value);
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

watch([nf, sort, pageSize, page], () => {
    rows.value = [];
    void load();
}, { immediate: true });
onScopeDispose(() => {
    requestId++;
    controller?.abort();
});

defineExpose({ refresh: load, loading });

const { t } = useI18n();
</script>

<style scoped>
.collection-ranking {
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
