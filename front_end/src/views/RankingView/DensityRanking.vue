<template>
    <section class="density-ranking">
        <div class="toolbar">
            <div class="board-buttons" :aria-label="t('local.board')">
                <BaseButton
                    v-for="option in boardOptions"
                    :key="option.code"
                    size="small"
                    :type="selectedLevel.code === option.code ? 'primary' : 'default'"
                    :plain="selectedLevel.code !== option.code"
                    :aria-pressed="selectedLevel.code === option.code"
                    @click="selectLevel(option)"
                >
                    {{ t('level.c', { row: option.row, column: option.column, mine: option.mine }) }}
                </BaseButton>
            </div>
        </div>

        <BaseTable v-loading="loading" class="ranking-table" :table-style="{ width: 'auto', marginInline: 'auto' }" :empty="players.length === 0" :empty-text="t('local.empty')" :column-count="7">
            <template #head>
                <tr>
                    <th scope="col" class="table-col-rank">
                        {{ t('prop.rank') }}
                    </th>
                    <th scope="col" class="table-col-player">
                        {{ t('prop.realName') }}
                    </th>
                    <th scope="col" class="table-col-number">
                        {{ t('prop.pluck') }}
                    </th>
                    <th scope="col" class="table-col-mode">
                        {{ t('prop.mode') }}
                    </th>
                    <th scope="col" class="table-col-number">
                        {{ t('prop.time') }}
                    </th>
                    <th scope="col" class="table-col-bv">
                        {{ t('prop.bv') }}
                    </th>
                    <th scope="col" class="table-col-datetime">
                        {{ t('prop.upload_time') }}
                    </th>
                </tr>
            </template>
            <tr v-for="(row, index) in players" :key="row.player_id">
                <td class="table-col-rank">
                    {{ getRank(index) }}
                </td>
                <td class="table-col-player">
                    <PlayerName :user-id="row.player_id" />
                </td>
                <td class="table-col-number">
                    <VideoPreviewLink :id="row.video_id">
                        {{ formatPluck(row.pluck) }}
                    </VideoPreviewLink>
                </td>
                <td class="table-col-mode">
                    {{ t(`mode.code${row.mode}`) }}
                </td>
                <td class="table-col-number">
                    {{ ms_to_s(row.timems) }}
                </td>
                <td class="table-col-bv">
                    {{ row.bv }}
                </td>
                <td class="table-col-datetime">
                    {{ formatDateTime(row.upload_time) }}
                </td>
            </tr>
        </BaseTable>

        <ElPagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            class="pagination"
            layout="total, sizes, prev, pager, next, jumper"
            :page-sizes="[20, 50, 100]"
            :total="totalCount"
        />
    </section>
</template>

<script setup lang="ts">
import { ElPagination, vLoading } from 'element-plus';
import { computed, onScopeDispose, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { queryChoice, queryInteger, useRankingQuery } from './useRankingQuery';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { httpErrorNotification } from '@/components/Notifications';
import PlayerName from '@/components/PlayerName.vue';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import $axios from '@/http';
import { fetchVideoInfos } from '@/services/videoInfoService';
import { ms_to_s } from '@/utils';
import { CustomLevel, DensityCustomLevelConfigs } from '@/utils/customlevel';
import { toISODateTimeString } from '@/utils/datetime';

interface RankPlayer {
    player_id: number;
    video_id: number;
    mode: string;
    pluck: number;
    timems: number;
    bv: number;
    upload_time: string;
}

interface RankResponse {
    count: number;
    players: Omit<RankPlayer, 'mode' | 'timems' | 'bv'>[];
}

const i18nMessages = {
    'zh-cn': { local: {
        board: '局面',
        empty: '暂无排行数据',
    } },
    en: { local: {
        board: 'Board',
        empty: 'No ranking data',
    } },
};

const { t } = useI18n({ messages: i18nMessages });

const boardOptions = ref<CustomLevel[]>([...DensityCustomLevelConfigs]);

const { fields: { level: levelCode, page: currentPage, page_size: pageSize } } = useRankingQuery(
    { level: 'c8_8_40', page: 1, page_size: 20 },
    (query, defaults) => ({ level: queryChoice(query.level, boardOptions.value.map((level) => level.code), defaults.level), page: queryInteger(query.page, defaults.page), page_size: queryChoice(query.page_size, [20, 50, 100], defaults.page_size) }),
    ['level', 'page_size'],
);
const selectedLevel = computed(() => boardOptions.value.find((level) => level.code === levelCode.value) ?? new CustomLevel(8, 8, 40));
const totalCount = ref(0);
const players = ref<RankPlayer[]>([]);
const loading = ref(false);
let requestId = 0;

async function fetchRanking() {
    const request = ++requestId;
    loading.value = true;
    const start = (currentPage.value - 1) * pageSize.value;
    const end = start + pageSize.value;
    try {
        const { data } = await $axios.get<RankResponse>('/api/customranking/pluck', {
            params: {
                level: selectedLevel.value.code,
                start,
                end,
            },
        });
        if (request !== requestId) return;
        const videos = await fetchVideoInfos(data.players.map((row) => ({ id: row.video_id, ongoing_tournament: false, ...row })));
        if (request !== requestId) return;
        players.value = videos.map((row) => ({ ...row, bv: row.bv ?? 0 }));
        totalCount.value = data.count;
    } catch (error) {
        if (request === requestId) httpErrorNotification(error);
    } finally {
        if (request === requestId) loading.value = false;
    }
}

function selectLevel(level: CustomLevel) {
    if (selectedLevel.value.code === level.code) return;
    levelCode.value = level.code;
}

function getRank(index: number): number {
    return (currentPage.value - 1) * pageSize.value + index + 1;
}

function formatPluck(value: number): string {
    return value.toFixed(6);
}

function formatDateTime(value: string): string {
    return toISODateTimeString(new Date(value));
}

watch([levelCode, currentPage, pageSize], () => {
    void fetchRanking();
}, { immediate: true });
onScopeDispose(() => {
    requestId++;
});
</script>

<style scoped>
.density-ranking {
    width: min(1120px, calc(100vw - 32px));
    margin: 0 auto;
}

.toolbar {
    margin: 12px 0 16px;
}

.board-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.board-buttons > .base-button {
    margin: 0;
}

.ranking-table {
    width: 100%;
}

.pagination {
    justify-content: center;
    margin-top: 16px;
}

@media (max-width: 640px) {
    .density-ranking {
        width: calc(100vw - 16px);
    }

    .toolbar {
        display: block;
    }

    .board-buttons {
        gap: 6px;
    }
}
</style>
