<template>
    <section class="history-panel" :aria-label="t('local.history')" :aria-busy="loading" data-cy="minigame-history-panel">
        <div class="history-filters">
            <label>{{ t('local.from') }}<input v-model="fromDate" type="date" :max="toDate || undefined" data-cy="minigame-history-from"></label>
            <label>{{ t('local.to') }}<input v-model="toDate" type="date" :min="fromDate || undefined" data-cy="minigame-history-to"></label>
            <BaseButton class="square-button" size="small" :title="t('button.refresh')" :aria-label="t('button.refresh')" :loading="loading" data-cy="minigame-history-refresh" @click="refresh++">
                <i class="pi pi-refresh" aria-hidden="true" />
            </BaseButton>
        </div>
        <p v-if="failed" role="alert" class="text text-danger text-small">
            {{ t('local.loadFailed') }}
        </p>
        <BaseTable :empty="entries.length === 0" :column-count="2" :empty-text="t(loading ? 'local.loading' : 'local.empty')">
            <template #head>
                <tr>
                    <th scope="col" :aria-sort="sort === 'date' ? 'descending' : 'none'">
                        <button type="button" class="stat-header" data-cy="minigame-history-date-sort" @click="sort = 'date'">
                            {{ t('local.date') }}
                        </button>
                    </th>
                    <th scope="col" class="table-col-number" :aria-sort="sort === 'score-asc' ? 'ascending' : sort === 'score-desc' ? 'descending' : 'none'">
                        <button type="button" class="stat-header" data-cy="minigame-history-score-sort" @click="sort = sort === 'score-asc' ? 'score-desc' : 'score-asc'">
                            {{ t('local.time') }}
                            <i v-if="sort !== 'date'" class="pi" :class="sort === 'score-asc' ? 'pi-sort-amount-up-alt' : 'pi-sort-amount-down'" aria-hidden="true" />
                        </button>
                    </th>
                </tr>
            </template>
            <tr v-for="entry in entries" :key="entry.id" tabindex="0" class="history-row" :data-history-id="entry.id" :aria-label="t('local.play', { date: toISODateTimeString(new Date(entry.playedAt)) })" @click="emit('play', entry.id)" @keydown.enter.prevent="emit('play', entry.id)" @keydown.space.prevent="emit('play', entry.id)">
                <td>{{ toISODateTimeString(new Date(entry.playedAt)) }}</td>
                <td class="table-col-number">
                    {{ ms_to_s(entry.scoreMs) }}
                </td>
            </tr>
        </BaseTable>
        <ElPagination v-model:current-page="page" :page-size="pageSize" :total="count" :disabled="loading" layout="total, prev, pager, next" :pager-count="5" small data-cy="minigame-history-pagination" />
    </section>
</template>

<script setup lang="ts">
import { ElPagination } from 'element-plus';
import { ref, shallowRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { ms_to_s } from '@/utils';
import { toISODateTimeString } from '@/utils/datetime';
import { minigameHistoryRevision, queryMinigameHistory } from '@/utils/minigame/history';
import type { MinigameHistoryMetadata, MinigameHistorySort } from '@/utils/minigame/history';

const props = defineProps({ rankingKey: { type: String, required: true } });
const emit = defineEmits<{ play: [id: number] }>();
const fromDate = ref('');
const toDate = ref('');
const sort = ref<MinigameHistorySort>('date');
const page = ref(1);
const pageSize = 20;
const count = ref(0);
const entries = shallowRef<MinigameHistoryMetadata[]>([]);
const loading = ref(false);
const failed = ref(false);
const refresh = ref(0);

function dateBoundary(value: string, nextDay = false): number | undefined {
    if (!value) return undefined;
    const date = new Date(`${value}T00:00:00`);
    if (nextDay) date.setDate(date.getDate() + 1);
    return date.getTime();
}

const filters = [() => props.rankingKey, fromDate, toDate, sort, minigameHistoryRevision, refresh] as const;
watch(filters, () => {
    page.value = 1;
}, { flush: 'sync' });
watch([...filters, page], async (_value, _old, onCleanup) => {
    let active = true;
    onCleanup(() => {
        active = false;
    });
    loading.value = true;
    failed.value = false;
    entries.value = [];
    try {
        const result = await queryMinigameHistory(props.rankingKey, { from: dateBoundary(fromDate.value), to: dateBoundary(toDate.value, true), sort: sort.value, offset: (page.value - 1) * pageSize, limit: pageSize });
        if (!active) return;
        entries.value = result.entries;
        count.value = result.count;
    } catch {
        if (active) {
            failed.value = true;
            count.value = 0;
        }
    } finally {
        if (active) loading.value = false;
    }
}, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: {
        history: '本地历史',
        from: '开始日期',
        to: '结束日期',
        date: '日期',
        time: '用时（秒）',
        play: '播放 {date} 的录像',
        loading: '正在读取本地历史…',
        empty: '暂无符合条件的本地纪录',
        loadFailed: '无法读取本地历史，请重试。',
    } },
    en: { local: {
        history: 'Local history',
        from: 'From',
        to: 'To',
        date: 'Date',
        time: 'Time (s)',
        play: 'Play replay from {date}',
        loading: 'Loading local history…',
        empty: 'No matching local results',
        loadFailed: 'Could not load local history. Please try again.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.history-panel {
    display: grid;
    gap: 8px;
    min-width: 0;
}

.history-filters {
    display: flex;
    align-items: end;
    flex-wrap: wrap;
    gap: 8px;
}

label {
    display: grid;
    gap: 4px;
    min-width: 0;
}

input {
    border: 1px solid var(--ui-border-color);
    padding: 4px;
    color: var(--ui-text-color-regular);
    background: var(--ui-fill-color-blank);
    font: inherit;
}

.history-row {
    cursor: pointer;
}

.history-row:is(:hover, :focus-visible) > td {
    background: var(--ui-color-primary-light-9);
}
</style>
