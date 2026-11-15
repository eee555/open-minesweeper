<template>
    <div class="saolei-import text-regular">
        <div v-if="owner" class="controls">
            <BaseButton size="small" :disabled="busy" :title="t('local.refreshFullHint')" data-cy="saolei-refresh-full" @click="runAction('full')">
                {{ t('local.refreshFull') }}
            </BaseButton>
            <BaseButton size="small" :disabled="busy" :title="t('local.refreshIncrementalHint')" data-cy="saolei-refresh-incremental" @click="runAction('incremental')">
                {{ t('local.refreshIncremental') }}
            </BaseButton>
            <BaseButton size="small" :disabled="busy" :title="t('local.importAllHint')" data-cy="saolei-import-all" @click="runAction('import')">
                {{ t('local.importAll') }}
            </BaseButton>
            <BaseButton v-if="busy" size="small" :disabled="stopping" @click="stopping = true">
                {{ t('local.stop') }}
            </BaseButton>
        </div>
        <p v-if="owner" class="text-small">
            {{ t('local.keepOpen') }}
            {{ t('local.supportedSoftware') }}
            <SoftwareIcon software="m" /> <SoftwareIcon software="r" /> <SoftwareIcon software="a" /> <SoftwareIcon software="e" />
            {{ t('local.importNotes') }}
        </p>
        <p v-if="progress">
            {{ t(progress.stage === 'catalogue' ? 'local.catalogueProgress' : 'local.importProgress', { ...progress }) }}
        </p>
        <p v-if="summary">
            {{ t('local.summary', { ...summary }) }}
        </p>
        <BaseTable :empty="pageRows.length === 0" :empty-text="t('local.empty')" :column-count="8" data-cy="saolei-import-table">
            <template #head>
                <tr>
                    <th scope="col" class="table-col-number" :aria-sort="sortState(sortOrder, sortField === 'remote_id')">
                        <span class="import-head">
                            <button type="button" class="import-head__sort" data-cy="sort-remote-id" @click="toggleSort('remote_id')">
                                <span>ID</span>
                                <SortIcon :state="sortState(sortOrder, sortField === 'remote_id')" class="import-head__sort-icon" :class="{ 'import-head__sort-icon--inactive': !isSortedColumn('remote_id') }" />
                            </button>
                        </span>
                    </th>
                    <th scope="col" class="table-col-datetime" :aria-sort="sortState(sortOrder, sortField === 'upload_time')">
                        <span class="import-head">
                            <button type="button" class="import-head__sort" data-cy="sort-upload-time" @click="toggleSort('upload_time')">
                                <span>{{ t('prop.upload_time') }}</span>
                                <SortIcon :state="sortState(sortOrder, sortField === 'upload_time')" class="import-head__sort-icon" :class="{ 'import-head__sort-icon--inactive': !isSortedColumn('upload_time') }" />
                            </button>
                        </span>
                    </th>
                    <th scope="col" class="table-col-center">
                        <span class="import-head">
                            <span>{{ t('prop.level') }}</span>
                            <Tippy interactive trigger="click" placement="bottom-start" :append-to="appendToBody">
                                <button type="button" class="import-head__filter" :aria-label="t('prop.level')" :title="t('prop.level')" data-cy="filter-level-trigger">
                                    <i class="pi" :class="filterIsClear('level') ? 'pi-filter' : 'pi-filter-fill'" aria-hidden="true" />
                                </button>
                                <template #content="{ hide }">
                                    <div class="card card-small import-filter-menu" @click.stop @keydown.esc="hide()">
                                        <BaseListbox :model-value="filterValue('level')" :options="levelOptions" :aria-label="t('prop.level')" data-cy="filter-level" @update:model-value="applyFilter('level', $event); hide()" />
                                    </div>
                                </template>
                            </Tippy>
                        </span>
                    </th>
                    <th scope="col" class="table-col-number" :aria-sort="sortState(sortOrder, sortField === 'timems')">
                        <span class="import-head">
                            <button type="button" class="import-head__sort" data-cy="sort-timems" @click="toggleSort('timems')">
                                <span>{{ t('prop.time') }}</span>
                                <SortIcon :state="sortState(sortOrder, sortField === 'timems')" class="import-head__sort-icon" :class="{ 'import-head__sort-icon--inactive': !isSortedColumn('timems') }" />
                            </button>
                        </span>
                    </th>
                    <th scope="col" class="table-col-bv" :aria-sort="sortState(sortOrder, sortField === 'bv')">
                        <span class="import-head">
                            <button type="button" class="import-head__sort" data-cy="sort-bv" @click="toggleSort('bv')">
                                <span>{{ t('prop.bv') }}</span>
                                <SortIcon :state="sortState(sortOrder, sortField === 'bv')" class="import-head__sort-icon" :class="{ 'import-head__sort-icon--inactive': !isSortedColumn('bv') }" />
                            </button>
                        </span>
                    </th>
                    <th scope="col" class="table-col-center" :aria-sort="sortState(sortOrder, sortField === 'software')">
                        <span class="import-head">
                            <button type="button" class="import-head__sort" data-cy="sort-software" @click="toggleSort('software')">
                                <span>{{ t('local.software') }}</span>
                                <SortIcon :state="sortState(sortOrder, sortField === 'software')" class="import-head__sort-icon" :class="{ 'import-head__sort-icon--inactive': !isSortedColumn('software') }" />
                            </button>
                        </span>
                    </th>
                    <th scope="col" class="table-col-center">
                        <span class="import-head">
                            <span>{{ t('prop.state') }}</span>
                            <Tippy interactive trigger="click" placement="bottom-start" :append-to="appendToBody">
                                <button type="button" class="import-head__filter" :aria-label="t('prop.state')" :title="t('prop.state')" data-cy="filter-import-status-trigger">
                                    <i class="pi" :class="filterIsClear('import_status') ? 'pi-filter' : 'pi-filter-fill'" aria-hidden="true" />
                                </button>
                                <template #content="{ hide }">
                                    <div class="card card-small import-filter-menu" @click.stop @keydown.esc="hide()">
                                        <BaseListbox :model-value="filterValue('import_status')" :options="statusOptions" :aria-label="t('prop.state')" data-cy="filter-import-status" @update:model-value="applyFilter('import_status', $event); hide()" />
                                    </div>
                                </template>
                            </Tippy>
                        </span>
                    </th>
                    <th scope="col" class="table-col-center" />
                </tr>
            </template>
            <tr v-for="row in pageRows" :key="row.id">
                <td class="table-col-number">
                    {{ row.remote_id }}
                </td>
                <td class="table-col-datetime">
                    {{ utc_to_local_format(row.upload_time) }}
                </td>
                <td class="table-col-center">
                    <GameLevelIcon :level="row.level" />
                </td>
                <td class="table-col-number">
                    {{ (row.timems / 1000).toFixed(3) }} <span v-if="row.nf">NF</span>
                </td>
                <td class="table-col-bv">
                    {{ row.bv }}
                </td>
                <td class="table-col-center">
                    {{ row.software }}
                </td>
                <td>
                    {{ t(`local.${row.import_status}`) }}
                    <span v-if="failures[row.id]" class="text-danger">{{ failures[row.id] }}</span>
                </td>
                <td class="table-col-center">
                    <VideoPreviewLink v-if="row.import_video !== null" :id="row.import_video" :aria-label="t('local.preview')">
                        <i class="pi pi-play-circle" />
                    </VideoPreviewLink>
                    <BaseButton v-else-if="owner && canImportSaoleiVideo(row)" size="small" :disabled="busy" data-cy="saolei-import-row" @click="importOne(row)">
                        {{ t('local.import') }}
                    </BaseButton>
                </td>
            </tr>
        </BaseTable>
        <BasePagination
            v-model:current-start="currentStart" v-model:page-size="pageSize"
            :total="total" :page-size-options="[5, 10, 25, 50, 100]" data-cy="saolei-import-pagination"
        />
    </div>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import 'primeicons/primeicons.css';

import { promiseTimeout } from '@vueuse/core';
import { isAxiosError } from 'axios';
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import type { ImportQueueFilters, SaoleiTableVideo, SortField } from './videoImportQueueData';
import { createImportQueueFilters, filterImportQueue, importStatuses, importStatusOf, sliceImportQueue, sortImportQueue } from './videoImportQueueData';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseListbox from '@/components/common/BaseListbox.vue';
import BasePagination from '@/components/common/BasePagination.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import SortIcon from '@/components/common/SortIcon.vue';
import { nextSortOrder, sortState } from '@/components/common/sortState';
import { httpErrorNotification } from '@/components/Notifications';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import GameLevelIcon from '@/components/widgets/GameLevelIcon.vue';
import SoftwareIcon from '@/components/widgets/SoftwareIcon.vue';
import { canImportSaoleiVideo, fetchSaoleiSummary, fetchSaoleiVideoPage, importPendingSaoleiVideos, importSaoleiVideo, refreshSaoleiCatalogue } from '@/services/saoleiSyncService';
import type { SaoleiSyncProgress } from '@/services/saoleiSyncService';
import type { SaoleiImportSummary, SaoleiVideo } from '@/utils/accountlinks';
import { MS_Levels } from '@/utils/ms_const';
import { utc_to_local_format } from '@/utils/system/tools';

const props = defineProps({
    saoleiId: { type: Number, required: true },
    owner: { type: Boolean, default: false },
});
const videos = ref<SaoleiVideo[]>([]);
const summary = ref<SaoleiImportSummary>();
const busy = ref(false);
const stopping = ref(false);
const progress = ref<SaoleiSyncProgress>();
const failures = ref<Record<number, string>>({});
const filters = reactive<ImportQueueFilters>(createImportQueueFilters());
const currentStart = ref(1);
const pageSize = ref(10);
const sortField = ref<SortField>('upload_time');
const sortOrder = ref<number | undefined>(-1);
const appendToBody = () => document.body;
let context = 0;

type ImportFilterField = keyof ImportQueueFilters;

const levelOptions = computed(() => [
    { value: null, label: t('local.all') },
    ...MS_Levels.map((level) => ({ value: level, label: t(`level.${level}`) })),
]);
const statusOptions = computed(() => [
    { value: null, label: t('local.all') },
    ...importStatuses.map((status) => ({ value: status, label: t(`local.${status}`) })),
]);
const tableData = computed<SaoleiTableVideo[]>(() => videos.value.map((video) => ({
    ...video, import_status: importStatusOf(video, canImportSaoleiVideo(video)),
})));
const processed = computed(() => sortImportQueue(filterImportQueue(tableData.value, filters), sortField.value, sortOrder.value));
const total = computed(() => processed.value.length);
const first = computed(() => Math.max(0, Math.min(currentStart.value, total.value) - 1));
const pageRows = computed(() => sliceImportQueue(processed.value, first.value, pageSize.value));

watch(filters, () => {
    currentStart.value = 1;
});

function filterIsClear(field: ImportFilterField): boolean {
    return filters[field] === null;
}

function filterValue<K extends ImportFilterField>(field: K): ImportQueueFilters[K] {
    return filters[field];
}

function applyFilter<K extends ImportFilterField>(field: K, value: ImportQueueFilters[K]) {
    filters[field] = value;
}

function isSortedColumn(field: SortField): boolean {
    return sortState(sortOrder.value, sortField.value === field) !== 'none';
}

function toggleSort(field: SortField) {
    const active = sortField.value === field;
    sortField.value = field;
    sortOrder.value = nextSortOrder(sortOrder.value, active);
    currentStart.value = 1;
}

async function refresh(current = context) {
    if (!props.saoleiId) return;
    try {
        const rows: SaoleiVideo[] = [];
        let after = 0;
        while (current === context) {
            const page = await fetchSaoleiVideoPage(props.saoleiId, after);
            if (current !== context) return;
            rows.push(...page.items);
            if (page.next_after === null) break;
            after = page.next_after;
            await promiseTimeout(250);
        }
        const stats = await fetchSaoleiSummary(props.saoleiId);
        if (current !== context) return;
        videos.value = rows;
        summary.value = stats;
    } catch (error) {
        if (current === context) httpErrorNotification(error);
    }
}

function recordFailure(id: number, error: unknown) {
    const data = isAxiosError<{ object?: string; category?: string }>(error) ? error.response?.data : undefined;
    failures.value[id] = data?.category !== undefined && data.category !== '' ? (data.object ?? 'file') + '/' + data.category : t('local.failed');
}

async function runAction(action: 'full' | 'incremental' | 'import') {
    if (busy.value || !props.owner) return;
    const current = context;
    const id = props.saoleiId;
    busy.value = true;
    stopping.value = false;
    failures.value = {};
    progress.value = undefined;
    const cancelled = () => current !== context || stopping.value;
    const report = (value: SaoleiSyncProgress) => {
        if (current === context) progress.value = value;
    };
    try {
        if (action === 'import') await importPendingSaoleiVideos(id, cancelled, report, recordFailure);
        else await refreshSaoleiCatalogue(id, action === 'full', cancelled, report);
    } catch (error) {
        if (current === context) httpErrorNotification(error);
    } finally {
        if (current === context) {
            await refresh(current);
            if (current === context) busy.value = false;
        }
    }
}

async function importOne(video: SaoleiVideo) {
    if (busy.value || !props.owner) return;
    const current = context;
    busy.value = true;
    try {
        await importSaoleiVideo(video.id);
    } catch (error) {
        if (current === context) recordFailure(video.id, error);
    } finally {
        if (current === context) {
            await refresh(current);
            if (current === context) busy.value = false;
        }
    }
}

watch(() => [props.saoleiId, props.owner] as const, () => {
    context++;
    videos.value = [];
    summary.value = undefined;
    progress.value = undefined;
    failures.value = {};
    busy.value = false;
    stopping.value = false;
    currentStart.value = 1;
    void refresh();
}, { immediate: true });
onBeforeUnmount(() => {
    context++;
});

const { t } = useI18n({ messages: {
    'zh-cn': { local: {
        refreshFull: '全量刷新列表',
        refreshFullHint: '从头逐页扫描全部录像目录，仅刷新列表，不导入录像。',
        refreshIncremental: '增量刷新列表',
        refreshIncrementalHint: '从上次保存的进度继续逐页扫描录像目录，仅刷新列表，不导入录像。',
        importAll: '导入全部录像',
        importAllHint: '逐个导入当前列表中符合条件的待导入录像；如需获取新录像，请先刷新列表。',
        stop: '停止后续操作',
        keepOpen: '操作期间请保持窗口打开；关闭或停止后可继续，已完成进度和已导入录像的关联、审核结果都会保留。',
        supportedSoftware: '仅接受',
        importNotes: '。导入失败的录像不再自动重试。',
        catalogueProgress: '已刷新 {pages} 页列表',
        importProgress: '已处理 {completed} 个录像，失败 {failed} 个',
        summary: '已收藏 {total}，已导入 {imported}，待导入 {pending}，拒收 {rejected}，不支持 {skipped}',
        software: '软件',
        all: '全部',
        empty: '暂无录像',
        imported: '已导入',
        pending: '待导入',
        rejected: '本站拒收',
        unsupported: '不支持的软件',
        preview: '预览录像',
        import: '导入',
        failed: '导入失败',
    } },
    en: { local: {
        refreshFull: 'Full list refresh',
        refreshFullHint: 'Scan the entire catalogue page by page from the beginning. Updates the list without importing replays.',
        refreshIncremental: 'Incremental list refresh',
        refreshIncrementalHint: 'Resume scanning the catalogue page by page from the saved cursor. Updates the list without importing replays.',
        importAll: 'Import all replays',
        importAllHint: 'Import eligible pending replays from the current list one at a time. Refresh the list first to find new replays.',
        stop: 'Stop further requests',
        keepOpen: 'Keep this window open during the operation. You can resume after stopping or closing it; completed progress, replay links and review results are preserved.',
        supportedSoftware: 'Only ',
        importNotes: ' are supported. Replays that fail to import are not retried automatically.',
        catalogueProgress: 'Refreshed {pages} list pages',
        importProgress: 'Processed {completed} replays; {failed} failed',
        summary: 'Collected {total}; imported {imported}; pending {pending}; rejected {rejected}; unsupported {skipped}',
        software: 'Software',
        all: 'All',
        empty: 'No replays',
        imported: 'Imported',
        pending: 'Pending',
        rejected: 'Rejected locally',
        unsupported: 'Unsupported software',
        preview: 'Preview replay',
        import: 'Import',
        failed: 'Import failed',
    } },
} });
</script>

<style scoped>
.controls {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5em;
}
.import-head {
    display: inline-flex;
    align-items: center;
    gap: 2px;
}

.import-head__sort,
.import-head__filter {
    margin: 0;
    border: 0;
    padding: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
}

.import-head__sort {
    display: inline-flex;
    align-items: center;
    gap: 2px;
}

.import-head__sort .import-head__sort-icon {
    font-size: 0.75em;
}

.import-head__sort .import-head__sort-icon--inactive {
    opacity: 0.45;
}

.import-head__sort:focus-visible,
.import-head__filter:focus-visible {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: 1px;
}

.import-head__filter {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1rem;
    height: 1rem;
    font-size: 0.75em;
}

.import-head__filter:hover {
    color: var(--ui-color-primary);
}

.import-filter-menu {
    display: flex;
    flex-direction: column;
    width: fit-content;
    max-width: calc(100vw - 2rem);
    padding: 6px;
}
</style>
