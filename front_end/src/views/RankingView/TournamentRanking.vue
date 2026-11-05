<template>
    <section class="tournament-ranking">
        <BaseTable
            v-loading="loading" :empty="rows.length === 0" :column-count="9"
            class="ranking-table"
            :empty-text="t('local.empty')"
        >
            <template #head>
                <tr>
                    <th scope="col" rowspan="2" class="table-col-rank" />
                    <th scope="col" rowspan="2" class="table-col-player" />
                    <th scope="colgroup" colspan="2" class="table-col-center">
                        {{ t('local.scoreGroup') }}
                    </th>
                    <th scope="colgroup" colspan="2" class="table-col-center">
                        {{ t('local.gscGroup') }}
                    </th>
                    <th scope="colgroup" colspan="3" class="table-col-center">
                        {{ t('local.weeklyGroup') }}
                    </th>
                </tr>
                <tr>
                    <th v-for="column in rankColumns" :key="column.field" scope="col" class="table-col-number">
                        <BaseTextButton
                            class="rank-header-button" :data-sort-field="column.field"
                            :type="sortBy === column.field ? 'primary' : 'default'" :aria-pressed="sortBy === column.field"
                            :aria-label="`${t(`local.${column.group}`)} ${t(`local.${column.label}`)}`"
                            @click="selectSort(column.field)"
                        >
                            {{ t(`local.${column.label}`) }}
                        </BaseTextButton>
                    </th>
                </tr>
            </template>
            <tr v-for="(row, index) in rows" :key="row.user_id">
                <td class="table-col-rank">
                    {{ first + index + 1 }}
                </td>
                <td class="table-col-player">
                    <PlayerName :user-id="row.user_id" />
                </td>
                <td class="table-col-number">
                    {{ formatScoreCurrent(row.score_current, row.last_updated) }}
                </td>
                <td class="table-col-number">
                    {{ row.score_total }}
                </td>
                <td class="table-col-number">
                    {{ row.gsc_total }}
                </td>
                <td class="table-col-number">
                    {{ formatGSCBest(row.gsc_best) }}
                </td>
                <td class="table-col-number">
                    {{ row.weekly_total }}
                </td>
                <td class="table-col-number">
                    {{ row.weekly_classic_total }}
                </td>
                <td class="table-col-number">
                    {{ formatWeeklyClassicBest(row.weekly_classic_best) }}
                </td>
            </tr>
        </BaseTable>

        <ElPagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            class="pagination"
            layout="total, sizes, prev, pager, next, jumper"
            :page-sizes="[20, 50, 100]"
            :total="total"
        />
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
import { httpErrorNotification } from '@/components/Notifications';
import PlayerName from '@/components/PlayerName.vue';
import { fetchTournamentUserRanking } from '@/services/tournamentService';
import type { TournamentUserRankField, TournamentUserRankingRow } from '@/services/tournamentService';
import { ms_to_s } from '@/utils';
import { globalNow } from '@/utils/datetime';
import { calculateTournamentScoreCurrent, decodeGSCBest, decodeWeeklyClassicBest } from '@/utils/tournamentUser';

const rankColumns = [
    { field: 'score_current', group: 'scoreGroup', label: 'scoreCurrent' },
    { field: 'score_total', group: 'scoreGroup', label: 'scoreTotal' },
    { field: 'gsc_total', group: 'gscGroup', label: 'gscTotal' },
    { field: 'gsc_best', group: 'gscGroup', label: 'gscBest' },
    { field: 'weekly_total', group: 'weeklyGroup', label: 'weeklyTotal' },
    { field: 'weekly_classic_total', group: 'weeklyGroup', label: 'weeklyClassicTotal' },
    { field: 'weekly_classic_best', group: 'weeklyGroup', label: 'weeklyClassicBest' },
] as const satisfies readonly { field: TournamentUserRankField; group: string; label: string }[];

const { fields: { sort: sortBy, page: currentPage, page_size: pageSize } } = useRankingQuery<{ sort: TournamentUserRankField; page: number; page_size: number }>(
    { sort: 'score_current', page: 1, page_size: 20 },
    (query, defaults) => ({ sort: queryChoice(query.sort, rankColumns.map((column) => column.field), defaults.sort), page: queryInteger(query.page, defaults.page), page_size: queryChoice(query.page_size, [20, 50, 100], defaults.page_size) }),
    ['sort', 'page_size'],
);
const total = ref(0);
const rows = ref<TournamentUserRankingRow[]>([]);
const loading = ref(false);
let requestId = 0;
const first = computed(() => (currentPage.value - 1) * pageSize.value);

async function fetchRanking() {
    const request = ++requestId;
    loading.value = true;
    try {
        const data = await fetchTournamentUserRanking({
            sortBy: sortBy.value,
            start: first.value,
            end: first.value + pageSize.value,
        });
        if (request !== requestId) return;
        rows.value = data.data;
        total.value = data.total;
    } catch (error) {
        if (request === requestId) httpErrorNotification(error);
    } finally {
        if (request === requestId) loading.value = false;
    }
}

function selectSort(field: TournamentUserRankField) {
    if (field === sortBy.value) return;
    sortBy.value = field;
}

function formatScoreCurrent(scoreCurrent: number, lastUpdated: string): string {
    return calculateTournamentScoreCurrent(scoreCurrent, lastUpdated, globalNow.value).toFixed(2);
}

function formatGSCBest(value: number): string {
    const best = decodeGSCBest(value);
    if (best === undefined) return '-';
    return `${ms_to_s(best.score)} / GSC#${best.order}`;
}

function formatWeeklyClassicBest(value: number): string {
    const best = decodeWeeklyClassicBest(value);
    if (best === undefined) return '-';
    return `${ms_to_s(best.score)} / ${best.year}-W${String(best.week).padStart(2, '0')}`;
}

watch([sortBy, currentPage, pageSize], () => {
    void fetchRanking();
}, { immediate: true });
onScopeDispose(() => {
    requestId++;
});

const i18nMessages = {
    'zh-cn': { local: {
        empty: '暂无比赛积分排行',
        gscBest: '最佳',
        gscGroup: '金羊杯',
        gscTotal: '总积分',
        scoreGroup: '总分',
        scoreCurrent: '当前积分',
        scoreTotal: '历史总积分',
        weeklyClassicBest: '经典模式最佳',
        weeklyClassicTotal: '经典模式总积分',
        weeklyGroup: '积分赛',
        weeklyTotal: '总积分',
    } },
    en: { local: {
        empty: 'No tournament ranking data',
        gscBest: 'Best',
        gscGroup: 'GSC',
        gscTotal: 'Total',
        scoreGroup: 'Overall',
        scoreCurrent: 'Current',
        scoreTotal: 'History Total',
        weeklyClassicBest: 'Classic Best',
        weeklyClassicTotal: 'Classic Total',
        weeklyGroup: 'Weekly',
        weeklyTotal: 'Total',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.tournament-ranking {
    width: min(1280px, calc(100vw - 32px));
    margin: 0 auto;
}

.ranking-table {
    width: 100%;
}

.rank-header-button {
    width: 100%;
    justify-content: flex-end;
    font: inherit;
}

.pagination {
    justify-content: center;
    margin-top: 16px;
}

@media (max-width: 640px) {
    .tournament-ranking {
        width: calc(100vw - 16px);
    }
}
</style>
