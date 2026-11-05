<template>
    <div class="saolei-import text-regular">
        <div v-if="owner" class="controls">
            <label><input v-model="full" type="checkbox" :disabled="busy"> {{ t('local.full') }}</label>
            <BaseButton size="small" :disabled="busy" data-cy="saolei-sync" @click="synchronize">
                {{ t('local.sync') }}
            </BaseButton>
            <BaseButton v-if="busy" size="small" :disabled="stopping" @click="stopping = true">
                {{ t('local.stop') }}
            </BaseButton>
        </div>
        <p v-if="owner" class="text-small">
            {{ t('local.keepOpen') }}
        </p>
        <p v-if="progress">
            {{ t('local.progress', { ...progress }) }}
        </p>
        <p v-if="summary">
            {{ t('local.summary', { ...summary }) }}
        </p>
        <PrDataTable
            v-model:filters="filters" :value="tableData" row-hover size="small"
            sort-field="upload_time" :sort-order="-1" paginator :rows="10" :rows-per-page-options="[5, 10, 25, 50, 100]"
            filter-display="menu"
        >
            <PrColumn field="remote_id" sortable header="ID" />
            <PrColumn field="upload_time" sortable :header="t('prop.upload_time')">
                <template #body="{ data }">
                    {{ utc_to_local_format(data.upload_time) }}
                </template>
            </PrColumn>
            <PrColumn field="level" :header="t('prop.level')" :show-filter-match-modes="false" :show-filter-operator="false">
                <template #body="{ data }">
                    <GameLevelIcon :level="data.level" />
                </template>
                <template #filter="{ filterModel, filterCallback }">
                    <PrListbox v-model="filterModel.value" :options="[...MS_Levels]" @change="filterCallback()" />
                </template>
            </PrColumn>
            <PrColumn field="timems" :header="t('prop.time')" sortable>
                <template #body="{ data }: { data: SaoleiVideo }">
                    {{ (data.timems / 1000).toFixed(3) }} <span v-if="data.nf">NF</span>
                </template>
            </PrColumn>
            <PrColumn field="bv" :header="t('prop.bv')" sortable />
            <PrColumn field="software" :header="t('local.software')" sortable />
            <PrColumn field="import_status" :header="t('prop.state')" :show-filter-match-modes="false" :show-filter-operator="false">
                <template #body="{ data }">
                    {{ t(`local.${ data.import_status}`) }}
                    <span v-if="failures[data.id]" class="text-danger">{{ failures[data.id] }}</span>
                </template>
                <template #filter="{ filterModel, filterCallback }">
                    <PrListbox v-model="filterModel.value" :options="['imported', 'pending', 'rejected', 'unsupported']" @change="filterCallback()">
                        <template #option="{ option }">
                            {{ t(`local.${ option}`) }}
                        </template>
                    </PrListbox>
                </template>
            </PrColumn>
            <PrColumn>
                <template #body="{ data }: { data: SaoleiVideo }">
                    <VideoPreviewLink v-if="data.import_video !== null" :id="data.import_video" :aria-label="t('local.preview')">
                        <i class="pi pi-play-circle" />
                    </VideoPreviewLink>
                    <BaseButton v-else-if="owner && canImportSaoleiVideo(data)" size="small" :disabled="busy" @click="importOne(data)">
                        {{ t('local.import') }}
                    </BaseButton>
                </template>
            </PrColumn>
        </PrDataTable>
    </div>
</template>

<script setup lang="ts">
import '@/styles/vendors/primevue-table.css';
import { FilterMatchMode } from '@primevue/core/api';
import { promiseTimeout } from '@vueuse/core';
import { isAxiosError } from 'axios';
import PrColumn from 'primevue/column';
import PrDataTable from 'primevue/datatable';
import PrListbox from 'primevue/listbox';
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import GameLevelIcon from '@/components/widgets/GameLevelIcon.vue';
import { canImportSaoleiVideo, fetchSaoleiSummary, fetchSaoleiVideoPage, importSaoleiVideo, synchronizeSaolei } from '@/services/saoleiSyncService';
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
const full = ref(false);
const busy = ref(false);
const stopping = ref(false);
const progress = ref<SaoleiSyncProgress>();
const failures = ref<Record<number, string>>({});
const filters = ref({
    level: { value: null, matchMode: FilterMatchMode.EQUALS },
    import_status: { value: null, matchMode: FilterMatchMode.EQUALS },
});
let context = 0;
const tableData = computed(() => videos.value.map((video) => ({
    ...video, import_status: video.import_video !== null ? 'imported' : video.import_rejected ? 'rejected' : canImportSaoleiVideo(video) ? 'pending' : 'unsupported',
})));

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

async function synchronize() {
    if (busy.value || !props.owner) return;
    const current = context;
    busy.value = true;
    stopping.value = false;
    failures.value = {};
    try {
        await synchronizeSaolei(props.saoleiId, full.value, () => current !== context || stopping.value, (value) => {
            if (current === context) progress.value = value;
        }, recordFailure);
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
    void refresh();
}, { immediate: true });
onBeforeUnmount(() => {
    context++;
});

const { t } = useI18n({ messages: {
    'zh-cn': { local: {
        full: '重新扫描全部目录',
        sync: '同步列表并导入录像',
        stop: '停止后续同步',
        keepOpen: '手动同步期间请保持窗口打开。关闭窗口或停止后，已完成进度仍会保留。',
        progress: '已同步 {pages} 页，已处理 {completed} 个录像，失败 {failed} 个',
        summary: '已收藏 {total}，已导入 {imported}，待导入 {pending}，拒收 {rejected}，不支持 {skipped}',
        software: '软件',
        imported: '已导入',
        pending: '待导入',
        rejected: '本站拒收',
        unsupported: '不支持的软件',
        preview: '预览录像',
        import: '导入',
        failed: '导入失败',
    } },
    en: { local: {
        full: 'Rescan the full catalogue',
        sync: 'Sync list and import replays',
        stop: 'Stop further requests',
        keepOpen: 'Keep this window open during manual sync. Completed progress is preserved when you stop or close it.',
        progress: 'Synced {pages} pages; processed {completed} replays; {failed} failed',
        summary: 'Collected {total}; imported {imported}; pending {pending}; rejected {rejected}; unsupported {skipped}',
        software: 'Software',
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
</style>
