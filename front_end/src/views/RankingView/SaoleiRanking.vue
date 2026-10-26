<template>
    <div style="display: flex; gap: 1rem; align-items: center">
        <label class="checkbox nf-toggle">
            <input v-model="nf" class="checkbox-input" type="checkbox">
            <span>{{ t('nf') }}</span>
        </label>
    </div>
    <ElAlert v-if="failed" :title="t('ranking.loadFailed')" type="error" :closable="false" />
    <BaseTable v-loading="loading" class="saolei-ranking-table" :table-style="{ width: 'auto', marginInline: 'auto' }" :empty="rows.length === 0" :column-count="2 + saoleiFields.length" :empty-text="t('ranking.empty')">
        <template #head>
            <tr>
                <th rowspan="2" scope="col" class="table-col-rank" />
                <th rowspan="2" scope="col" class="table-col-player">
                    {{ t('prop.player') }}
                </th>
                <th v-for="level in levels" :key="level" colspan="2" scope="colgroup" class="table-col-center">
                    {{ t(`level.${level}`) }}
                </th>
            </tr>
            <tr>
                <template v-for="level in levels" :key="level">
                    <th scope="col" class="table-col-number">
                        <SaoleiRankingColumn :level="level" stat="t" :selected="stat" @select="selectStat" />
                    </th>
                    <th scope="col" class="table-col-number">
                        <SaoleiRankingColumn :level="level" stat="b" :selected="stat" @select="selectStat" />
                    </th>
                </template>
            </tr>
        </template>
        <tr v-for="(row, index) in rows" :key="row.player_id">
            <td class="table-col-rank">
                {{ first + index + 1 }}
            </td>
            <td class="table-col-player">
                <PlayerName :user-id="row.player_id" />
            </td>
            <td v-for="field in saoleiFields" :key="field" class="table-col-number" :style="cellStyle(row, field)">
                <VideoPreviewLink v-if="saoleiVideoId(row, field)" :id="saoleiVideoId(row, field)">
                    {{ formatSaoleiValue(row, field) }}
                </VideoPreviewLink>
                <span v-else>{{ formatSaoleiValue(row, field) }}</span>
            </td>
        </tr>
    </BaseTable>
    <div class="pagination">
        <ElPagination
            v-model:current-page="currentPage" v-model:page-size="pageSize"
            layout="total, sizes, prev, pager, next, jumper" :page-sizes="[20, 50, 100]" :total="total"
        />
    </div>
</template>

<script setup lang="ts">
import '@/styles/button.css';

import { ElAlert, ElPagination, vLoading } from 'element-plus';
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import SaoleiRankingColumn from './SaoleiRankingColumn.vue';
import { queryChoice, queryInteger, queryNF, useRankingQuery } from './useRankingQuery';

import BaseTable from '@/components/common/BaseTable.vue';
import PlayerName from '@/components/PlayerName.vue';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import { fetchSaoleiRanking, formatSaoleiValue, isSaoleiTimeStat, saoleiFields, SaoleiLevels, saoleiVideoId } from '@/services/saoleiRankingService';
import type { SaoleiField, SaoleiRecord } from '@/services/saoleiRankingService';
import { colorThemes } from '@/store/color';
import { getPiecewiseColorSchemeName } from '@/utils/ms_const';

const props = defineProps({ colored: { type: Boolean, default: false } });

const levels = [...SaoleiLevels, 'sum'] as const;
const { fields: { nf, sort: stat, page: currentPage, page_size: pageSize }, update } = useRankingQuery<{ nf: boolean; sort: SaoleiField; page: number; page_size: number }>(
    { nf: false, sort: 'sumt', page: 1, page_size: 20 },
    (query, defaults) => ({ nf: queryNF(query.nf), sort: queryChoice(query.sort, saoleiFields, defaults.sort), page: queryInteger(query.page, defaults.page), page_size: queryChoice(query.page_size, [20, 50, 100], defaults.page_size) }),
    ['nf', 'sort', 'page_size'],
);
const first = computed(() => (currentPage.value - 1) * pageSize.value);
const total = ref(0);
const rows = ref<SaoleiRecord[]>([]);
const loading = ref(false);
const failed = ref(false);
let requestId = 0;

function cellStyle(row: SaoleiRecord, field: SaoleiField) {
    const cellLevel = SaoleiLevels.find((candidateLevel) => field.startsWith(candidateLevel));
    const value = row[field];
    if (!props.colored || cellLevel === undefined || value === null) return undefined;
    const cellStat = isSaoleiTimeStat(field) ? 'time' : 'bvs';
    return colorThemes[getPiecewiseColorSchemeName(cellStat, cellLevel)].value.getStyle(cellStat === 'time' ? value / 1000 : value);
}

async function load() {
    const current = ++requestId;
    loading.value = true;
    failed.value = false;
    try {
        const data = await fetchSaoleiRanking(nf.value ? 'saolei_nf' : 'saolei', stat.value, first.value, first.value + pageSize.value);
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

function selectStat(selected: SaoleiField) {
    if (selected === stat.value) return;
    stat.value = selected;
}

watch([nf, stat, pageSize, currentPage], () => {
    rows.value = [];
    void load();
}, { immediate: true });

defineExpose({ refresh: load, loading });

const { t } = useI18n();
</script>

<style scoped>
.pagination {
    margin-top: 1rem;
    overflow-x: auto;
}

.pagination > :deep(.el-pagination) {
    width: max-content;
    margin-inline: auto;
}
</style>
