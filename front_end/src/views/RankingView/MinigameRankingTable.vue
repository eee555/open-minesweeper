<template>
    <ElAlert v-if="failed" :title="t('ranking.loadFailed')" type="error" :closable="false" />
    <BaseTable v-loading="loading" class="minigame-ranking-table" :table-style="{ width: 'auto', marginInline: 'auto' }" :empty="rows.length === 0" :column-count="rankings.length + 2" :empty-text="t('ranking.empty')">
        <template #head>
            <tr>
                <th :rowspan="hasDensities ? 2 : 1" scope="col" class="table-col-rank">
                    <button v-if="hasDensities" type="button" class="stat-header" :title="t('local.switchDisplay', { metric: t(displayCes ? 'prop.time' : 'prop.ces') })" :aria-label="t('local.switchDisplay', { metric: t(displayCes ? 'prop.time' : 'prop.ces') })" data-cy="minigame-ranking-score-display" @click="minigameSettings.leftClickScoreDisplay = displayCes ? 'time' : 'ces'">
                        {{ t(displayCes ? 'prop.ces' : 'prop.time') }}
                    </button>
                </th>
                <th :rowspan="hasDensities ? 2 : 1" scope="col" class="table-col-player">
                    {{ t('prop.player') }}
                </th>
                <template v-if="hasDensities">
                    <th v-for="level in ['b', 'i', 'e']" :key="level" scope="colgroup" colspan="3" class="table-col-center">
                        {{ t(`level.${level}`) }}
                    </th>
                </template>
                <template v-else>
                    <th v-for="ranking in rankings" :key="ranking.key" scope="col" class="table-col-number" :aria-sort="sort === ranking.key ? sortDirection(ranking) : 'none'">
                        <button type="button" class="stat-header" :aria-pressed="sort === ranking.key" @click="sort = ranking.key">
                            {{ t(`level.${ranking.level}`) }}
                        </button>
                    </th>
                </template>
            </tr>
            <tr v-if="hasDensities">
                <th v-for="ranking in rankings" :key="ranking.key" scope="col" class="table-col-number" :aria-sort="sort === ranking.key ? sortDirection(ranking) : 'none'">
                    <button type="button" class="stat-header" :aria-label="`${t(`level.${ranking.level}`)} ${densityLabels[ranking.density ?? '50']}`" :aria-pressed="sort === ranking.key" @click="sort = ranking.key">
                        {{ densityLabels[ranking.density ?? '50'] }}
                    </button>
                </th>
            </tr>
        </template>
        <tr v-for="row in rows" :key="row.player_id">
            <td class="table-col-rank">
                {{ row.rank }}
            </td>
            <td class="table-col-player">
                <PlayerName :user-id="row.player_id" />
            </td>
            <td v-for="ranking in rankings" :key="ranking.key" class="table-col-number" :style="cellStyle(row, ranking)" :title="row.records[ranking.key] == null ? undefined : toISODateTimeString(new Date(row.records[ranking.key]!.achieved_at))">
                <RouterLink v-if="row.records[ranking.key] != null" class="link" data-cy="minigame-replay-link" :to="{ name: `minigame-${game}`, query: { player: row.player_id, key: ranking.key.slice(game.length + 1) } }">
                    {{ formatMinigameScore(row.records[ranking.key]!.score, ranking.key, minigameSettings.leftClickScoreDisplay) }}
                </RouterLink>
                <template v-else>
                    --
                </template>
            </td>
        </tr>
    </BaseTable>
    <div class="pagination">
        <ElPagination v-model:current-page="page" v-model:page-size="pageSize" layout="total, sizes, prev, pager, next, jumper" :page-sizes="[20, 50, 100]" :total="total" />
    </div>
</template>

<script setup lang="ts">
import '@/styles/link.css';

import { ElAlert, ElPagination, vLoading } from 'element-plus';
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink } from 'vue-router';

import { queryChoice, queryInteger, useRankingQuery } from './useRankingQuery';

import BaseTable from '@/components/common/BaseTable.vue';
import PlayerName from '@/components/PlayerName.vue';
import { fetchMinigameRanking, fetchMinigameRankings } from '@/services/minigameRankingService';
import type { MinigameColorScheme, MinigameRanking, MinigameRankingRow } from '@/services/minigameRankingService';
import { toISODateTimeString } from '@/utils/datetime';
import type { TrainingGame } from '@/utils/minigame/games';
import { formatMinigameScore } from '@/utils/minigame/scoreDisplay';
import { minigameSettings } from '@/utils/minigame/settings';

const props = defineProps({
    game: { type: String as PropType<TrainingGame>, required: true },
    colorScheme: { type: Function as PropType<MinigameColorScheme>, default: undefined },
});
const rankings = ref<MinigameRanking[]>([]);
const hasDensities = computed(() => props.game === 'left-click' || props.game === 'multi-touch');
const displayCes = computed(() => hasDensities.value && minigameSettings.value.leftClickScoreDisplay === 'ces');
const densityLabels = { 50: '1/2', 75: '3/4', 87.5: '7/8' };
const { fields: { sort, page, page_size: pageSize }, update } = useRankingQuery(
    { sort: '', page: 1, page_size: 20 },
    (query, defaults) => ({ sort: queryChoice(query.sort, rankings.value.map((ranking) => ranking.key), rankings.value[0]?.key ?? defaults.sort), page: queryInteger(query.page, defaults.page), page_size: queryChoice(query.page_size, [20, 50, 100], defaults.page_size) }),
    ['sort', 'page_size'],
);
const first = computed(() => (page.value - 1) * pageSize.value);
const rows = ref<MinigameRankingRow[]>([]);
const total = ref(0);
const loading = ref(false);
const failed = ref(false);
let requestId = 0;

function sortDirection(ranking: MinigameRanking) {
    if (displayCes.value) return ranking.order === 'asc' ? 'descending' : 'ascending';
    return ranking.order === 'asc' ? 'ascending' : 'descending';
}

function cellStyle(row: MinigameRankingRow, ranking: MinigameRanking) {
    const record = row.records[ranking.key];
    return record == null ? undefined : props.colorScheme?.(ranking, record.score);
}

async function load() {
    const current = ++requestId;
    loading.value = true;
    failed.value = false;
    try {
        if (!rankings.value.length) {
            const definitions = await fetchMinigameRankings();
            if (current !== requestId) return;
            rankings.value = definitions.find((group) => group.game === props.game)?.rankings ?? [];
            if (!rankings.value.length) throw new Error('Missing minigame rankings');
            // Updating metadata also updates the parsed default sort and triggers this watcher.
            return;
        }
        const data = await fetchMinigameRanking(props.game, sort.value, first.value, first.value + pageSize.value);
        if (current !== requestId) return;
        rows.value = data.players;
        total.value = data.count;
        if (first.value > 0 && first.value >= total.value) void update({ page: Math.max(1, Math.ceil(total.value / pageSize.value)) }, true);
    } catch {
        if (current !== requestId) return;
        rows.value = [];
        total.value = 0;
        failed.value = true;
    } finally {
        if (current === requestId) loading.value = false;
    }
}

watch([sort, page, pageSize], () => {
    rows.value = [];
    void load();
}, { immediate: true });
onBeforeUnmount(() => {
    requestId++;
});
defineExpose({ refresh: load, loading });
const i18nMessages = {
    'zh-cn': { local: { switchDisplay: '切换为 {metric}' } },
    en: { local: { switchDisplay: 'Switch to {metric}' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.stat-header {
    display: block;
    width: 100%;
    padding: 0;
    border: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: right;
    cursor: pointer;
}

.stat-header[aria-pressed="true"] {
    color: var(--ui-color-primary);
}

.pagination {
    margin-top: 1rem;
    overflow-x: auto;
}

.pagination > :deep(.el-pagination) {
    width: max-content;
    margin-inline: auto;
}
</style>
