<template>
    <section v-loading="loading">
        <div class="msgames-controls">
            <BaseButton size="small" :disabled="loading || sending" @click="refresh()">
                {{ t('action.refresh') }}
            </BaseButton>
            <template v-if="owner">
                <BaseButton size="small" :disabled="loading || sending" @click="sync">
                    {{ t('local.sync') }}
                </BaseButton>
                <BaseButton size="small" :disabled="loading || sending" @click="importAll">
                    {{ t('local.importAll') }}
                </BaseButton>
                <BaseButton v-if="batching" size="small" :disabled="stopping" @click="stopping = true">
                    {{ t('local.stop') }}
                </BaseButton>
            </template>
            <span v-if="summary">{{ t('local.summary', { total: summary.total, imported: summary.imported }) }}</span>
            <span v-if="progress">{{ t('local.progress', progress) }}</span>
        </div>
        <p v-if="summary?.video_update_time">
            {{ t('local.updated') }}: {{ summary.video_update_time }}
        </p>
        <BaseTable
            :empty="pageRows.length === 0" :empty-text="t('local.empty')" :column-count="5"
            table-class="msgames-videos" data-cy="msgames-import-table"
        >
            <template #head>
                <tr>
                    <th scope="col" class="table-col-datetime" :aria-sort="sortState(sortOrder)">
                        <BaseButton size="small" text :aria-label="t('local.date')" data-cy="sort-upload-date" @click="toggleSort">
                            {{ t('local.date') }}
                            <SortIcon :state="sortState(sortOrder)" />
                        </BaseButton>
                    </th>
                    <th scope="col">
                        {{ t('local.source') }}
                    </th>
                    <th scope="col">
                        <div class="msgames-filter-header">
                            <span>{{ t('local.category') }}</span>
                            <input v-model="filters.category" class="msgames-filter-control" type="text" :aria-label="t('local.categoryQuery')" :placeholder="t('local.categoryQuery')" data-cy="filter-category">
                        </div>
                    </th>
                    <th scope="col">
                        {{ t('local.score') }}
                    </th>
                    <th scope="col">
                        <div class="msgames-filter-header">
                            <span>{{ t('button.import') }}</span>
                            <select v-model="filters.import_status" class="msgames-filter-control" :aria-label="t('local.statusFilter')" data-cy="filter-import-status">
                                <option :value="null">
                                    {{ t('local.allStatuses') }}
                                </option>
                                <option v-for="status in msgamesImportStatuses" :key="status" :value="status">
                                    {{ t(status === 'imported' ? 'accountlink.importStatus.successful' : `local.${status}`) }}
                                </option>
                            </select>
                        </div>
                    </th>
                </tr>
            </template>
            <tr v-for="row in pageRows" :key="row.id">
                <td class="table-col-datetime">
                    {{ row.upload_date ?? '--' }}
                </td>
                <td>
                    <a :href="row.url" target="_blank" rel="noopener noreferrer">{{ row.filename }}</a>
                </td>
                <td class="msgames-text">
                    {{ row.category }}
                </td>
                <td class="msgames-text">
                    {{ row.score }}
                </td>
                <td>
                    <VideoPreviewLink v-if="row.import_video !== null" :id="row.import_video">
                        #{{ row.import_video }}
                    </VideoPreviewLink>
                    <span v-else-if="row.import_status === 'unsupported'">{{ t('local.unsupported') }}</span>
                    <BaseButton v-else-if="owner" size="small" :disabled="sending" data-cy="msgames-import-row" @click="importOne(row)">
                        {{ row.import_status === 'failed' ? t('button.retry') : t('button.import') }}
                    </BaseButton>
                    <span v-if="row.import_status === 'importing'">{{ t('local.importing') }}</span>
                    <span v-else-if="row.import_status === 'failed'">{{ t('local.failed') }}: {{ failures[row.id] }}</span>
                    <span v-else-if="row.import_status === 'pending' && !owner">{{ t('local.pending') }}</span>
                </td>
            </tr>
        </BaseTable>
        <BasePagination
            v-model:current-start="currentStart" v-model:page-size="pageSize"
            :total="total" :page-size-options="[10, 25, 50, 100]" data-cy="msgames-import-pagination"
        />
    </section>
</template>

<script setup lang="ts">
import { promiseTimeout } from '@vueuse/core';
import { isAxiosError } from 'axios';
import { vLoading } from 'element-plus';
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import type { MSGamesImportQueueFilters, MSGamesTableVideo } from './msgamesImportQueueData';
import {
    createMSGamesImportQueueFilters, filterMSGamesImportQueue, msgamesImportStatuses,
    msgamesImportStatusOf, sliceMSGamesImportQueue, sortMSGamesImportQueue,
} from './msgamesImportQueueData';

import BaseButton from '@/components/common/BaseButton.vue';
import BasePagination from '@/components/common/BasePagination.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import SortIcon from '@/components/common/SortIcon.vue';
import { nextSortOrder, sortState } from '@/components/common/sortState';
import { httpErrorNotification } from '@/components/Notifications';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import { fetchMSGamesImportSummary, fetchMSGamesVideos, importMSGamesVideo, syncMSGamesVideos } from '@/services/accountLinkService';
import type { MSGamesImportSummary, MSGamesVideo } from '@/utils/accountlinks';
import { canImportMSGamesVideo } from '@/utils/accountlinks';

const props = defineProps({
    msgamesId: { type: Number, required: true },
    owner: { type: Boolean, required: true },
});
const videos = ref<MSGamesVideo[]>([]);
const summary = ref<MSGamesImportSummary>();
const currentStart = ref(1);
const pageSize = ref(10);
const sortOrder = ref<number | undefined>(-1);
const filters = reactive<MSGamesImportQueueFilters>(createMSGamesImportQueueFilters());
const loading = ref(false);
const sending = ref(false);
const batching = ref(false);
const stopping = ref(false);
const importingId = ref<number>();
const failures = ref<Record<number, string>>({});
const progress = ref<{ completed: number; total: number; failed: number }>();
let generation = 0;
let context = 0;

const tableData = computed<MSGamesTableVideo[]>(() => videos.value.map((video) => ({
    ...video, import_status: msgamesImportStatusOf(video, canImportMSGamesVideo(video), importingId.value, failures.value),
})));
const processed = computed(() => sortMSGamesImportQueue(filterMSGamesImportQueue(tableData.value, filters), sortOrder.value));
const total = computed(() => processed.value.length);
const first = computed(() => Math.max(0, Math.min(currentStart.value, total.value) - 1));
const pageRows = computed(() => sliceMSGamesImportQueue(processed.value, first.value, pageSize.value));

watch(filters, () => {
    currentStart.value = 1;
});

function toggleSort() {
    sortOrder.value = nextSortOrder(sortOrder.value, true, -1);
    currentStart.value = 1;
}

async function refresh(shouldContinue: () => boolean = () => true): Promise<boolean> {
    const current = ++generation;
    if (!props.msgamesId) return false;
    const active = () => current === generation && shouldContinue();
    loading.value = true;
    try {
        const [result, stats] = await Promise.all([
            fetchMSGamesVideos(props.msgamesId), fetchMSGamesImportSummary(props.msgamesId),
        ]);
        if (!active()) return false;
        videos.value = result;
        if (currentStart.value > result.length) currentStart.value = 1;
        summary.value = stats;
        return true;
    } catch (error) {
        if (current === generation) httpErrorNotification(error);
        return false;
    } finally {
        if (current === generation) loading.value = false;
    }
}

watch(() => props.msgamesId, () => {
    context++;
    generation++;
    videos.value = [];
    summary.value = undefined;
    currentStart.value = 1;
    Object.assign(filters, createMSGamesImportQueueFilters());
    loading.value = false;
    sending.value = false;
    batching.value = false;
    stopping.value = false;
    importingId.value = undefined;
    failures.value = {};
    progress.value = undefined;
    void refresh();
}, { immediate: true });

async function sync() {
    if (sending.value) return;
    const current = context;
    sending.value = true;
    try {
        await syncMSGamesVideos(props.msgamesId);
        if (current === context) await refresh();
    } catch (error) {
        if (current === context) httpErrorNotification(error);
    } finally {
        if (current === context) sending.value = false;
    }
}

function errorDescription(error: unknown): string {
    if (isAxiosError<{ object?: string; category?: string }>(error)) {
        const data = error.response?.data;
        if (data?.category !== undefined && data.category !== '') return `${data.object ?? 'import'}/${data.category}`;
    }
    return t('local.requestFailed');
}

async function importVideo(video: MSGamesVideo, current: number): Promise<boolean> {
    importingId.value = video.id;
    failures.value[video.id] = '';
    try {
        const result = await importMSGamesVideo(video.id);
        if (current !== context) return false;
        video.import_video = result.import_video_id;
        const visible = videos.value.find((item) => item.id === video.id);
        if (visible) visible.import_video = result.import_video_id;
        if (summary.value) summary.value.imported++;
        return true;
    } catch (error) {
        if (current === context) failures.value[video.id] = errorDescription(error);
        return false;
    } finally {
        if (current === context) importingId.value = undefined;
    }
}

async function importOne(video: MSGamesVideo) {
    if (sending.value) return;
    const current = context;
    sending.value = true;
    try {
        await importVideo(video, current);
        if (current === context) await refresh();
    } finally {
        if (current === context) sending.value = false;
    }
}

async function importAll() {
    if (sending.value) return;
    const current = context;
    const account = props.msgamesId;
    const cancelled = () => current !== context || stopping.value;
    sending.value = true;
    batching.value = true;
    stopping.value = false;
    progress.value = undefined;
    try {
        await syncMSGamesVideos(account);
        if (cancelled()) return;
        if (!await refresh(() => !cancelled()) || cancelled()) return;
        const pending = videos.value.filter((video) => video.import_video === null && canImportMSGamesVideo(video));
        progress.value = { completed: 0, total: pending.length, failed: 0 };
        for (const video of pending) {
            if (cancelled()) break;
            const success = await importVideo(video, current);
            if (current !== context) return;
            progress.value.completed++;
            if (!success) progress.value.failed++;
            if (progress.value.completed < pending.length && !cancelled()) await promiseTimeout(1100);
        }
    } catch (error) {
        if (current === context) httpErrorNotification(error);
    } finally {
        if (current === context) {
            await refresh();
            if (current === context) {
                sending.value = false;
                batching.value = false;
            }
        }
    }
}

onBeforeUnmount(() => {
    context++;
    generation++;
});

const { t } = useI18n({ messages: {
    'zh-cn': { local: {
        sync: '同步录像列表',
        importAll: '导入未导入录像',
        stop: '停止后续导入',
        importing: '正在导入',
        failed: '导入失败',
        requestFailed: '请求失败',
        progress: '已处理 {completed}/{total}，失败 {failed} 个',
        date: '上传日期',
        source: '原始录像',
        category: '分类',
        score: '成绩',
        unsupported: '暂不支持此配置或格式',
        empty: '暂无已同步录像',
        categoryQuery: '查询分类',
        statusFilter: '筛选导入状态',
        allStatuses: '全部状态',
        pending: '未导入',
        summary: '共 {total} 个，已导入 {imported} 个',
        updated: '列表更新时间',
    } },
    en: { local: {
        sync: 'Sync video list',
        importAll: 'Import remaining videos',
        stop: 'Stop further imports',
        importing: 'Importing',
        failed: 'Import failed',
        requestFailed: 'Request failed',
        progress: '{completed}/{total} processed, {failed} failed',
        date: 'Upload date',
        source: 'Original replay',
        category: 'Category',
        score: 'Score',
        unsupported: 'Unsupported board or format',
        empty: 'No synced videos',
        categoryQuery: 'Search category',
        statusFilter: 'Filter import status',
        allStatuses: 'All statuses',
        pending: 'Not imported',
        summary: '{total} videos, {imported} imported',
        updated: 'List updated',
    } },
} });
</script>

<style scoped>
.msgames-controls {
    display: flex;
    gap: 0.5em;
    align-items: center;
    flex-wrap: wrap;
    margin: 0.5em 0;
}
.msgames-text {
    white-space: pre-line;
}
.msgames-videos td {
    vertical-align: top;
    overflow-wrap: anywhere;
}
.msgames-filter-control {
    font: inherit;
    color: var(--el-text-color-primary);
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color);
    padding: 0.4em;
}
.msgames-filter-header {
    display: flex;
    align-items: center;
    gap: 0.5em;
    white-space: nowrap;
}
</style>
