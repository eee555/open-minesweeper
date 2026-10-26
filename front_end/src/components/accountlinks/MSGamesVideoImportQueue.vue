<template>
    <section v-loading="loading">
        <div class="msgames-controls">
            <BaseButton size="small" :disabled="loading || sending" @click="refresh()">
                {{ t('common.action.refresh') }}
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
        <PrDataTable
            v-model:filters="filters" v-model:first="first" v-model:rows="rows"
            :value="tableData" data-key="id" size="small" row-hover
            sort-field="upload_date" :sort-order="-1"
            paginator :rows-per-page-options="[10, 25, 50, 100]"
            paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown CurrentPageReport"
            current-page-report-template="{first}–{last} / {totalRecords}"
            class="msgames-videos"
        >
            <template #empty>
                {{ t('local.empty') }}
            </template>
            <PrColumn field="upload_date" :header="t('local.date')" sortable>
                <template #body="{ data }: { data: MSGamesTableVideo }">
                    {{ data.upload_date ?? '--' }}
                </template>
            </PrColumn>
            <PrColumn field="filename" :header="t('local.source')">
                <template #body="{ data }: { data: MSGamesTableVideo }">
                    <a :href="data.url" target="_blank" rel="noopener noreferrer">{{ data.filename }}</a>
                </template>
            </PrColumn>
            <PrColumn field="category" :show-filter-menu="false" body-class="msgames-text">
                <template #header>
                    <div class="msgames-filter-header">
                        <span>{{ t('local.category') }}</span>
                        <PrInputText v-model="filters.category.value" :aria-label="t('local.categoryQuery')" :placeholder="t('local.categoryQuery')" />
                    </div>
                </template>
            </PrColumn>
            <PrColumn field="score" :header="t('local.score')" body-class="msgames-text" />
            <PrColumn field="import_status" :show-filter-menu="false">
                <template #header>
                    <div class="msgames-filter-header">
                        <span>{{ t('common.button.import') }}</span>
                        <select v-model="filters.import_status.value" :aria-label="t('local.statusFilter')" class="msgames-status-filter">
                            <option :value="null">
                                {{ t('local.allStatuses') }}
                            </option>
                            <option v-for="status in importStatuses" :key="status" :value="status">
                                {{ t(status === 'imported' ? 'accountlink.importStatus.successful' : `local.${status}`) }}
                            </option>
                        </select>
                    </div>
                </template>
                <template #body="{ data }: { data: MSGamesTableVideo }">
                    <VideoPreviewLink v-if="data.import_video" :id="data.import_video">
                        #{{ data.import_video }}
                    </VideoPreviewLink>
                    <span v-else-if="data.import_status === 'unsupported'">{{ t('local.unsupported') }}</span>
                    <BaseButton v-else-if="owner" size="small" :disabled="sending" @click="importOne(data)">
                        {{ data.import_status === 'failed' ? t('common.button.retry') : t('common.button.import') }}
                    </BaseButton>
                    <span v-if="data.import_status === 'importing'">{{ t('local.importing') }}</span>
                    <span v-else-if="data.import_status === 'failed'">{{ t('local.failed') }}: {{ failures[data.id] }}</span>
                    <span v-else-if="data.import_status === 'pending' && !owner">{{ t('local.pending') }}</span>
                </template>
            </PrColumn>
        </PrDataTable>
    </section>
</template>

<script setup lang="ts">
import { FilterMatchMode } from '@primevue/core/api';
import { promiseTimeout } from '@vueuse/core';
import { isAxiosError } from 'axios';
import { vLoading } from 'element-plus';
import PrColumn from 'primevue/column';
import PrDataTable from 'primevue/datatable';
import PrInputText from 'primevue/inputtext';
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
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
const first = ref(0);
const rows = ref(10);
const importStatuses = ['pending', 'importing', 'imported', 'failed', 'unsupported'] as const;
type ImportStatus = typeof importStatuses[number];
type MSGamesTableVideo = MSGamesVideo & { import_status: ImportStatus };
const initialFilters = () => ({
    category: { value: '', matchMode: FilterMatchMode.CONTAINS },
    import_status: { value: null as ImportStatus | null, matchMode: FilterMatchMode.EQUALS },
});
const filters = ref(initialFilters());
watch([() => filters.value.category.value, () => filters.value.import_status.value], () => first.value = 0);
const loading = ref(false);
const sending = ref(false);
const batching = ref(false);
const stopping = ref(false);
const importingId = ref<number>();
const failures = ref<Record<number, string>>({});
const progress = ref<{ completed: number; total: number; failed: number }>();
let generation = 0;
let context = 0;

const tableData = computed<MSGamesTableVideo[]>(() => videos.value.map((video) => ({ ...video, import_status: importStatus(video) })));

function importStatus(video: MSGamesVideo): ImportStatus {
    if (video.import_video !== null) return 'imported';
    if (!canImportMSGamesVideo(video)) return 'unsupported';
    if (importingId.value === video.id) return 'importing';
    if ((failures.value[video.id] ?? '') !== '') return 'failed';
    return 'pending';
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
        if (first.value >= result.length) first.value = 0;
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
    first.value = 0;
    filters.value = initialFilters();
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
:deep(.msgames-text) {
    white-space: pre-line;
}
:deep(.msgames-videos td) {
    vertical-align: top;
    overflow-wrap: anywhere;
}
.msgames-status-filter {
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
:deep(.p-inputtext), :deep(.p-select) {
    border-radius: 0;
}
</style>
