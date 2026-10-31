<template>
    <section class="pb-ranking">
        <div class="pb-toolbar">
            <label class="checkbox nf-toggle">
                <input v-model="nf" class="checkbox-input" type="checkbox">
                <span>{{ t('nf') }}</span>
            </label>
            <PBBVButton v-for="optionLevel in pbLevels" :key="optionLevel" :level="optionLevel" :selected-level="level" :selected-bv="bv" :nf="nf" :counts="counts" @select="selectBucket(optionLevel, $event)" />
        </div>
        <ElAlert v-if="failed" :title="t('ranking.loadFailed')" type="error" :closable="false" />
        <ElAlert v-if="countsFailed" :title="t('local.countsFailed')" type="error" :closable="false" />
        <PBRankingTable :rows="rows" :level="level" :bv="bv" :first="first" :loading="loading" :colored="colored" />
        <div class="pb-pagination">
            <ElPagination v-model:current-page="currentPage" v-model:page-size="pageSize" layout="total, sizes, prev, pager, next, jumper" :page-sizes="[20, 50, 100]" :total="total" />
        </div>
    </section>
</template>

<script setup lang="ts">
import { ElAlert, ElPagination } from 'element-plus';
import { computed, onMounted, onScopeDispose, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import PBBVButton from './PBBVButton.vue';
import PBRankingTable from './PBRankingTable.vue';
import { queryChoice, queryInteger, queryNF, useRankingQuery } from './useRankingQuery';

import { fetchPBCounts, fetchPBRanking, pbBVLimits, pbLevels } from '@/services/pbRankingService';
import type { PBCounts, PBRankingPlayer } from '@/services/pbRankingService';
import type { MS_Level } from '@/utils/ms_const';

defineProps({ colored: { type: Boolean, default: false } });

const { fields: { level, bv, nf, page: currentPage, page_size: pageSize }, update } = useRankingQuery<{ level: MS_Level; bv: number; nf: boolean; page: number; page_size: number }>(
    { level: 'b', bv: 1, nf: false, page: 1, page_size: 20 },
    (query, defaults) => {
        const selectedLevel = queryChoice(query.level, pbLevels, defaults.level);
        return { level: selectedLevel, bv: queryInteger(query.bv, defaults.bv, pbBVLimits[selectedLevel].max), nf: queryNF(query.nf), page: queryInteger(query.page, defaults.page), page_size: queryChoice(query.page_size, [20, 50, 100], defaults.page_size) };
    },
    ['level', 'bv', 'nf', 'page_size'],
);
const counts = ref<PBCounts>({});
const countsLoading = ref(false);
const countsFailed = ref(false);
const first = computed(() => (currentPage.value - 1) * pageSize.value);
const total = ref(0);
const rows = ref<PBRankingPlayer[]>([]);
const loading = ref(false);
const failed = ref(false);
let requestId = 0;
let countsRequestId = 0;

function selectBucket(selectedLevel: MS_Level, selectedBV: number) {
    void update({ level: selectedLevel, bv: selectedBV });
}

async function loadCounts() {
    const current = ++countsRequestId;
    countsLoading.value = true;
    countsFailed.value = false;
    try {
        const data = await fetchPBCounts();
        if (current === countsRequestId) counts.value = data;
    } catch {
        if (current === countsRequestId) countsFailed.value = true;
    } finally {
        if (current === countsRequestId) countsLoading.value = false;
    }
}

function refresh() {
    void loadCounts();
    void load();
}

async function load() {
    const current = ++requestId;
    loading.value = true;
    failed.value = false;
    try {
        const data = await fetchPBRanking(level.value, bv.value, nf.value, first.value, first.value + pageSize.value);
        if (current !== requestId) return;
        rows.value = data.players;
        total.value = data.count;
        if (first.value > 0 && first.value >= total.value) {
            void update({ page: Math.max(1, Math.ceil(total.value / pageSize.value)) }, true);
        }
    } catch {
        if (current !== requestId) return;
        rows.value = [];
        total.value = 0;
        failed.value = true;
    } finally {
        if (current === requestId) loading.value = false;
    }
}

watch([level, bv, nf, pageSize, currentPage], () => {
    rows.value = [];
    void load();
}, { immediate: true });
onMounted(() => {
    void loadCounts();
});
onScopeDispose(() => {
    requestId++;
    countsRequestId++;
});

defineExpose({ refresh, loading: computed(() => loading.value || countsLoading.value) });

const i18nMessages = {
    'zh-cn': { local: {
        countsFailed: '各榜人数加载失败',
    } },
    en: { local: {
        countsFailed: 'Unable to load board counts',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.pb-ranking {
    min-width: 0;
}

.pb-toolbar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 8px;
}

.pb-pagination {
    margin-top: 8px;
    overflow-x: auto;
}

.pb-pagination > :deep(.el-pagination) {
    width: max-content;
    margin-inline: auto;
}
</style>
