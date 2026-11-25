<template>
    <section class="path-ranking">
        <p v-if="failed" role="alert" class="text-danger">
            {{ t('ranking.loadFailed') }}
        </p>
        <BaseTable v-loading="loading" table-class="path-ranking-table" :empty="players.length === 0" :column-count="14" :empty-text="t('ranking.empty')" :table-style="{ width: 'auto', marginInline: 'auto' }">
            <template #head>
                <tr>
                    <th scope="col" rowspan="2" class="table-col-rank">
                        #
                    </th>
                    <th scope="col" rowspan="2" class="table-col-player">
                        {{ t('prop.player') }}
                    </th>
                    <th v-for="group in pathGroups" :key="group" scope="colgroup" colspan="3" class="path-group table-col-center">
                        {{ t(`level.${group}`) }}
                    </th>
                </tr>
                <tr>
                    <th v-for="column in pathColumns" :key="column.stat" scope="col" class="table-col-number" :class="{ 'path-group': column.metric === 'path' }" :aria-sort="sort === column.stat ? 'ascending' : 'none'">
                        <BaseTextButton :type="sort === column.stat ? 'primary' : 'default'" :data-field="column.stat" :aria-label="`${t(`level.${column.level}`)} ${column.label}`" :aria-pressed="sort === column.stat" @click="sort = column.stat">
                            {{ column.label }}
                        </BaseTextButton>
                    </th>
                </tr>
            </template>
            <tr v-for="(player, index) in players" :key="player.player_id">
                <td class="table-col-rank">
                    {{ currentStart + index }}
                </td>
                <td class="table-col-player">
                    <PlayerName :user-id="player.player_id" />
                </td>
                <td v-for="column in pathColumns" :key="column.stat" class="table-col-number" :class="{ 'path-group': column.metric === 'path' }" :data-field="column.stat" :title="String(pathValue(player, column.stat) ?? '--')">
                    <VideoPreviewLink v-if="pathVideoId(player, column.stat)" :id="pathVideoId(player, column.stat)">
                        {{ formatPathValue(player, column.stat) }}
                    </VideoPreviewLink>
                    <template v-else>
                        {{ formatPathValue(player, column.stat) }}
                    </template>
                </td>
            </tr>
        </BaseTable>
        <BasePagination v-if="total > 0 && currentStart <= total" v-model:page-size="pageSize" :current-start="currentStart" :total="total" :page-size-options="[20, 50, 100]" @change="changeRange" />
    </section>
</template>

<script setup lang="ts">
import { vLoading } from 'element-plus';
import { onScopeDispose, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { queryChoice, queryInteger, useRankingQuery } from './useRankingQuery';

import BasePagination from '@/components/common/BasePagination.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import type { PaginationRange } from '@/components/common/pagination';
import PlayerName from '@/components/PlayerName.vue';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import { fetchPathRanking, formatPathValue, pathColumns, pathGroups, pathStats, pathValue, pathVideoId } from '@/services/pathRankingService';
import type { PathRecord, PathStat } from '@/services/pathRankingService';

const { fields: { sort, start: currentStart, page_size: queryPageSize }, update } = useRankingQuery<{ sort: PathStat; start: number; page_size: number }>(
    { sort: 'sum_epath', start: 1, page_size: 20 },
    (query, defaults) => ({ sort: queryChoice(query.sort, pathStats, defaults.sort), start: queryInteger(query.start, defaults.start), page_size: queryChoice(query.page_size, [20, 50, 100], defaults.page_size) }),
    ['sort', 'page_size'],
);
// Keep a local page size so the pagination's two model updates produce one URL change.
const pageSize = ref(queryPageSize.value);
watch(queryPageSize, (value) => {
    pageSize.value = value;
});
function changeRange(range: PaginationRange) {
    void update({ start: range.start, page_size: pageSize.value });
}
const players = ref<PathRecord[]>([]);
const total = ref(0);
const loading = ref(false);
const failed = ref(false);
let requestId = 0;
let controller: AbortController | undefined;

async function load() {
    controller?.abort();
    controller = new AbortController();
    const { signal } = controller;
    const request = ++requestId;
    loading.value = true;
    failed.value = false;
    try {
        const start = currentStart.value - 1;
        const result = await fetchPathRanking(sort.value, start, start + queryPageSize.value, signal);
        if (request !== requestId) return;
        players.value = result.players;
        total.value = result.count;
        if (start > 0 && start >= total.value) void update({ start: Math.max(1, total.value - queryPageSize.value + 1) }, true);
    } catch {
        if (signal.aborted || request !== requestId) return;
        failed.value = true;
        players.value = [];
        total.value = 0;
    } finally {
        if (request === requestId) loading.value = false;
    }
}
watch([sort, currentStart, queryPageSize], () => {
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
.path-ranking {
    display: grid;
    gap: 8px;
    min-width: 0;
}

:deep(.path-group) {
    border-left: 2px solid var(--ui-border-color);
}
</style>
