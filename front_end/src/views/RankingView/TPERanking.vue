<template>
    <section class="tpe-ranking">
        <p v-if="failed" role="alert" class="text-danger">
            {{ t('ranking.loadFailed') }}
        </p>
        <BaseTable v-loading="loading" class="tpe-ranking-table" :empty="players.length === 0" :column-count="5" :empty-text="t('ranking.empty')" :table-style="{ width: 'auto', marginInline: 'auto' }">
            <template #head>
                <tr>
                    <th scope="col" class="table-col-rank">
                        #
                    </th>
                    <th scope="col" class="table-col-player">
                        {{ t('prop.player') }}
                    </th>
                    <th v-for="field in tpeStats" :key="field" scope="col" class="table-col-number" :aria-sort="sort === field ? 'ascending' : 'none'">
                        <BaseTextButton :type="sort === field ? 'primary' : 'default'" :data-field="field" :aria-pressed="sort === field" @click="sort = field">
                            {{ t(`level.${field}`) }}
                        </BaseTextButton>
                    </th>
                </tr>
            </template>
            <tr v-for="(player, index) in players" :key="player.player_id">
                <td class="table-col-rank">
                    {{ start + index + 1 }}
                </td>
                <td class="table-col-player">
                    <PlayerName :user-id="player.player_id" />
                </td>
                <td v-for="field in tpeStats" :key="field" class="table-col-number" :data-field="field" :title="String(tpeValue(player, field) ?? '--')" :style="cellStyle(player, field)">
                    <VideoPreviewLink v-if="tpeVideoId(player, field)" :id="tpeVideoId(player, field)">
                        {{ formatTPEValue(player, field) }}
                    </VideoPreviewLink>
                    <template v-else>
                        {{ formatTPEValue(player, field) }}
                    </template>
                </td>
            </tr>
        </BaseTable>
        <div class="tpe-pagination">
            <ElPagination v-model:current-page="page" v-model:page-size="pageSize" layout="total, sizes, prev, pager, next, jumper" :page-sizes="[20, 50, 100]" :total="total" />
        </div>
    </section>
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus-select.css';
import { ElPagination, vLoading } from 'element-plus';
import { computed, onScopeDispose, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { queryChoice, queryInteger, useRankingQuery } from './useRankingQuery';

import BaseTable from '@/components/common/BaseTable.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import PlayerName from '@/components/PlayerName.vue';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import { fetchTPERanking, formatTPEValue, tpeStats, tpeValue, tpeVideoId } from '@/services/tpeRankingService';
import type { TPERecord, TPEStat } from '@/services/tpeRankingService';
import { colorThemes } from '@/store/color';

const props = defineProps({ colored: { type: Boolean, default: false } });
const { fields: { sort, page, page_size: pageSize }, update } = useRankingQuery<{ sort: TPEStat; page: number; page_size: number }>(
    { sort: 'sum', page: 1, page_size: 20 },
    (query, defaults) => ({ sort: queryChoice(query.sort, tpeStats, defaults.sort), page: queryInteger(query.page, defaults.page), page_size: queryChoice(query.page_size, [20, 50, 100], defaults.page_size) }),
    ['sort', 'page_size'],
);
const start = computed(() => (page.value - 1) * pageSize.value);
const players = ref<TPERecord[]>([]);
const total = ref(0);
const loading = ref(false);
const failed = ref(false);
let requestId = 0;
let controller: AbortController | undefined;

function cellStyle(player: TPERecord, field: TPEStat) {
    const value = tpeValue(player, field);
    if (!props.colored || field === 'sum' || value === null) return undefined;
    return colorThemes[`${field}time`].value.getStyle(value);
}

async function load() {
    controller?.abort();
    controller = new AbortController();
    const { signal } = controller;
    const request = ++requestId;
    loading.value = true;
    failed.value = false;
    try {
        const result = await fetchTPERanking(sort.value, start.value, start.value + pageSize.value, signal);
        if (request !== requestId) return;
        players.value = result.players;
        total.value = result.count;
        if (start.value > 0 && start.value >= total.value) void update({ page: Math.max(1, Math.ceil(total.value / pageSize.value)) }, true);
    } catch {
        if (signal.aborted || request !== requestId) return;
        failed.value = true;
        players.value = [];
        total.value = 0;
    } finally {
        if (request === requestId) loading.value = false;
    }
}

watch([sort, page, pageSize], () => {
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
.tpe-ranking {
    min-width: 0;
}

.tpe-pagination {
    margin-top: 8px;
    overflow-x: auto;
}

.tpe-pagination > :deep(.el-pagination) {
    width: max-content;
    margin-inline: auto;
}
</style>
