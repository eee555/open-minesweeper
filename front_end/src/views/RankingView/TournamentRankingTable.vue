<template>
    <section>
        <BaseTable v-loading="loading" :empty="rows.length === 0" :column-count="columns.length + 2" class="ranking-table" :empty-text="t('local.empty')">
            <template #head>
                <tr>
                    <th scope="col" class="table-col-rank" />
                    <th scope="col" class="table-col-player">
                        {{ t('prop.realName') }}
                    </th>
                    <th v-for="column in columns" :key="column.field" scope="col" class="table-col-number">
                        <span v-if="column.field === 'edition'">{{ t('local.edition') }}</span>
                        <BaseTextButton v-else class="rank-header-button" :data-sort-field="column.field" :type="sortBy === column.field ? 'primary' : 'default'" :aria-pressed="sortBy === column.field" @click="sortBy = column.field">
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
                <td v-for="column in columns" :key="column.field" class="table-col-number">
                    {{ displayValue(row, column.field) }}
                </td>
            </tr>
        </BaseTable>
        <ElPagination v-model:current-page="currentPage" v-model:page-size="pageSize" class="pagination" layout="total, sizes, prev, pager, next, jumper" :page-sizes="[20, 50, 100]" :total="total" />
    </section>
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus-select.css';
import { ElPagination, vLoading } from 'element-plus';
import { computed, onScopeDispose, ref, watch } from 'vue';
import type { PropType } from 'vue';
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

type RankingKind = 'overall' | 'gsc' | 'weekly' | 'weekly_eff';
interface Column { field: TournamentUserRankField | 'edition'; label: string }
const props = defineProps({ kind: { type: String as PropType<RankingKind>, default: 'overall' } });
const columnSets: Record<RankingKind, Column[]> = {
    overall: [
        { field: 'score_current', label: 'current' }, { field: 'score_total', label: 'historical' },
        { field: 'gsc_total', label: 'gsc' }, { field: 'weekly_total', label: 'weekly' }, { field: 'weekly_eff_total', label: 'weeklyEff' },
    ],
    gsc: [{ field: 'gsc_total', label: 'total' }, { field: 'gsc_best', label: 'best' }, { field: 'edition', label: 'edition' }],
    weekly: [{ field: 'weekly_total', label: 'total' }, { field: 'weekly_classic_best', label: 'best' }, { field: 'edition', label: 'edition' }],
    weekly_eff: [{ field: 'weekly_eff_total', label: 'total' }, { field: 'weekly_eff_best', label: 'best' }, { field: 'edition', label: 'edition' }],
};
const columns = computed(() => columnSets[props.kind]);
const rankFields = computed(() => columns.value.map((column) => column.field).filter((field): field is TournamentUserRankField => field !== 'edition'));
const { fields: { sort: sortBy, page: currentPage, page_size: pageSize } } = useRankingQuery<{ sort: TournamentUserRankField; page: number; page_size: number }>(
    { sort: rankFields.value[0], page: 1, page_size: 20 },
    (query, defaults) => ({ sort: queryChoice(query.sort, rankFields.value, defaults.sort), page: queryInteger(query.page, defaults.page), page_size: queryChoice(query.page_size, [20, 50, 100], defaults.page_size) }),
    ['sort', 'page_size'],
);
const total = ref(0);
const rows = ref<TournamentUserRankingRow[]>([]);
const loading = ref(false);
const first = computed(() => (currentPage.value - 1) * pageSize.value);
let requestId = 0;

async function fetchRanking() {
    const request = ++requestId;
    loading.value = true;
    try {
        const result = await fetchTournamentUserRanking({ sortBy: sortBy.value, start: first.value, end: first.value + pageSize.value });
        if (request !== requestId) return;
        rows.value = result.data;
        total.value = result.total;
    } catch (error) {
        if (request === requestId) httpErrorNotification(error);
    } finally {
        if (request === requestId) loading.value = false;
    }
}

function weekEdition(year: number | null, week: number | null): string {
    return year === null || week === null ? '-' : `${year}-W${String(week).padStart(2, '0')}`;
}

function displayValue(row: TournamentUserRankingRow, field: Column['field']): string {
    if (field === 'score_current') return calculateTournamentScoreCurrent(row.score_current, row.last_updated, globalNow.value).toFixed(2);
    if (field === 'gsc_best') {
        const best = decodeGSCBest(row.gsc_best);
        return best ? ms_to_s(best.score) : '-';
    }
    if (field === 'weekly_classic_best') {
        const best = decodeWeeklyClassicBest(row.weekly_classic_best);
        return best ? ms_to_s(best.score) : '-';
    }
    if (field === 'weekly_eff_best') return row.weekly_eff_best === null ? '-' : row.weekly_eff_best.toFixed(3);
    if (field === 'edition') {
        if (props.kind === 'gsc') {
            const best = decodeGSCBest(row.gsc_best);
            return best ? `GSC#${best.order}` : '-';
        }
        if (props.kind === 'weekly') {
            const best = decodeWeeklyClassicBest(row.weekly_classic_best);
            return best ? weekEdition(best.year, best.week) : '-';
        }
        return weekEdition(row.weekly_eff_best_year, row.weekly_eff_best_week);
    }
    return String(row[field]);
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
        current: '当前积分',
        historical: '历史总积分',
        gsc: 'GSC 总积分',
        weekly: '竞速打卡赛总积分',
        weeklyEff: '效率打卡赛总积分',
        total: '总积分',
        best: '历史最好成绩',
        edition: '取得最好成绩的届号',
    } },
    en: { local: {
        empty: 'No tournament ranking data',
        current: 'Current',
        historical: 'History Total',
        gsc: 'GSC Total',
        weekly: 'Speed Weekly Total',
        weeklyEff: 'Efficiency Weekly Total',
        total: 'Total',
        best: 'Best',
        edition: 'Best Edition',
    } },
    es: { local: {
        empty: 'Sin datos de clasificación de torneo',
        current: 'Actual',
        historical: 'Historial Total',
        gsc: 'Total GSC',
        weekly: 'Velocidad Semanal Total',
        weeklyEff: 'Eficiencia Semanal Total',
        total: 'Total',
        best: 'Mejor',
        edition: 'Edición Mejor',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.rank-header-button {
    width: 100%;
    justify-content: flex-end;
    font: inherit;
}

.pagination {
    justify-content: center;
    margin-top: 1rem;
}
</style>
