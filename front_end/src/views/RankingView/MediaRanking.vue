<template>
    <section class="media-ranking">
        <div class="media-toolbar">
            <BaseTextButton underline="never" :aria-pressed="sortBy === 'hot'" @click="sortBy = 'hot'">
                {{ t('media.sortHot') }}
            </BaseTextButton>
            <BaseTextButton underline="never" :aria-pressed="sortBy === 'likes'" @click="sortBy = 'likes'">
                {{ t('media.sortLikes') }}
            </BaseTextButton>
        </div>
        <BaseTable :empty="rows.length === 0" :empty-text="t('media.empty')" :column-count="4">
            <template #head>
                <tr>
                    <th scope="col" class="table-col-rank">
                        #
                    </th>
                    <th scope="col">
                        {{ t('media.player') }}
                    </th>
                    <th scope="col">
                        {{ t('media.sortHot') }}
                    </th>
                    <th scope="col">
                        {{ t('media.sortLikes') }}
                    </th>
                </tr>
            </template>
            <tr v-for="(row, index) in rows" :key="row.user_id">
                <td class="table-col-rank">
                    {{ start + index + 1 }}
                </td>
                <td><PlayerName :user-id="row.user_id" /></td>
                <td>{{ realHot(row).toFixed(2) }}</td>
                <td>{{ row.likes }}</td>
            </tr>
        </BaseTable>
        <ElPagination v-model:current-page="page" v-model:page-size="pageSize" layout="total, prev, pager, next" :total="total" />
    </section>
</template>

<script setup lang="ts">
import { ElPagination } from 'element-plus';
import { computed, onScopeDispose, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import type { LocationQuery } from 'vue-router';

import { queryChoice, queryInteger, useRankingQuery } from './useRankingQuery';

import BaseTable from '@/components/common/BaseTable.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import PlayerName from '@/components/PlayerName.vue';
import type { MediaUserRankRow } from '@/services/mediaService';
import { fetchUserMediaRanking } from '@/services/mediaService';

import '@/components/media/media.css';

const { t } = useI18n();

const defaults: { sort: 'hot' | 'likes'; page: number; page_size: number } = { sort: 'hot', page: 1, page_size: 20 };
function parse(query: LocationQuery, fallback: typeof defaults): typeof defaults {
    return {
        sort: queryChoice(query.sort, ['hot', 'likes'] as const, fallback.sort),
        page: queryInteger(query.page, fallback.page),
        page_size: queryInteger(query.page_size, fallback.page_size, 50),
    };
}
const { fields: { sort: sortBy, page, page_size: pageSize } } = useRankingQuery(defaults, parse, ['sort', 'page_size']);

// 榜单 Redis 分数以 anchor 为时间基准，展示时按 0.99/天折算成当前时刻的实时热度。
const MEDIA_HOT_DAILY_RETENTION = 0.99;
const MS_PER_DAY = 86400000;

const rows = ref<MediaUserRankRow[]>([]);
const total = ref(0);
const anchor = ref<string | null>(null);
const observedAt = ref(Date.now());
const start = computed(() => (page.value - 1) * pageSize.value);
let requestId = 0;

function realHot(row: MediaUserRankRow): number {
    const base = anchor.value === null ? observedAt.value : new Date(anchor.value).getTime();
    if (!Number.isFinite(base)) return row.hot;
    return row.hot * MEDIA_HOT_DAILY_RETENTION ** ((observedAt.value - base) / MS_PER_DAY);
}

async function load(): Promise<void> {
    const request = ++requestId;
    try {
        const result = await fetchUserMediaRanking(sortBy.value, start.value, pageSize.value);
        if (request !== requestId) return;
        rows.value = result.items;
        total.value = result.total;
        anchor.value = result.anchor;
        observedAt.value = Date.now();
    } catch (error) {
        if (request !== requestId) return;
        rows.value = [];
        total.value = 0;
        anchor.value = null;
        httpErrorNotification(error);
    }
}

watch([sortBy, page, pageSize], () => {
    void load();
}, { immediate: true });
onScopeDispose(() => {
    requestId++;
});
</script>
