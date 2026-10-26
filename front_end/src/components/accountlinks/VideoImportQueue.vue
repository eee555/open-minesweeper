<template>
    <PrDataTable
        v-model:filters="filters"
        v-loading="importing"
        element-loading-background="rgba(122, 122, 122, 0.4)"
        :value="tableData" row-hover size="small"
        sort-field="upload_time" :sort-order="-1"
        paginator :rows="10" :rows-per-page-options="[5, 10, 25, 50, 100]"
        paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown JumpToPageInput CurrentPageReport"
        :filter-button-props="{
            filter: {
                severity: 'secondary',
                text: true,
                rounded: false,
                size: 'small',
                style: { borderRadius: '0', padding: '0', width: '1rem' }
            }
        }"
        filter-display="menu"
    >
        <PrColumn field="id" sortable header="ID" />
        <PrColumn field="upload_time" sortable :header="t('prop.upload_time')" style="min-width: 11em">
            <template #body="{ data }">
                <span class="text">
                    {{ utc_to_local_format(data.upload_time) }}
                </span>
            </template>
        </PrColumn>
        <PrColumn field="level" :show-filter-match-modes="false" :show-filter-operator="false" style="width: 5em" :filter-header-style="{ marginInlineStart: '0px' }">
            <template #body="{ data }">
                <GameLevelIcon :level="data.level" />
            </template>
            <template #filter="{ filterModel, applyFilter }">
                <PrListbox v-model="filterModel.value" :options="[...MS_Levels]" @change="applyFilter()">
                    <template #option="slotProps">
                        <GameLevelIcon :level="slotProps.option" />
                    </template>
                </PrListbox>
            </template>
        </PrColumn>
        <PrColumn field="timems" :header="t('prop.time')" sortable>
            <template #body="{ data }: { data: SaoleiVideo }">
                {{ (data.timems / 1000).toFixed(2) }}
                <span v-if="data.nf" class="text-warning">
                    NF
                </span>
            </template>
        </PrColumn>
        <PrColumn field="bv" :header="t('prop.bv')" sortable />
        <PrColumn field="import_task__status" :header="t('prop.state')" :show-filter-match-modes="false" :show-filter-operator="false" :show-apply-button="false" :show-clear-button="false" :filter-header-style="{ marginInlineStart: '0px' }">
            <template #body="{ data }: { data: SaoleiVideo }">
                <span v-if="data.import_task__status == 'RUNNING'" class="text-warning">
                    {{ t('accountlink.importStatus.running') }}
                </span>
                <span v-else-if="data.import_task__status == 'SUCCESSFUL' && data.import_video__id != 0" class="text-success">
                    {{ t('accountlink.importStatus.successful') }}（新）
                </span>
                <span v-else-if="data.import_task__status == 'FAILED'" class="text-danger">
                    {{ t('accountlink.importStatus.failed') }}
                </span>
                <span v-else-if="data.import_task__status == 'READY'" class="text-primary">
                    {{ t('accountlink.importStatus.ready') }}
                </span>
                <span v-else-if="data.import_task__status == 'SUCCESSFUL' && data.import_video__id == 0" class="text-danger">
                    {{ t('accountlink.importStatus.connection') }}
                </span>
                <span v-else-if="data.import_task__status == 'NULL' && data.import_video__id != 0" class="text-success">
                    {{ t('accountlink.importStatus.successful') }}
                </span>
            </template>
            <template #filter="{ filterModel, filterCallback }">
                <PrListbox v-model="filterModel.value" :options="[...DjangoTaskResultStatusOptions]" @change="filterCallback()">
                    <template #option="slotProps">
                        <DjangoTaskResultStatusBadge :status="slotProps.option" />
                    </template>
                </PrListbox>
            </template>
        </PrColumn>
        <PrColumn>
            <template #body="{ data }: { data: SaoleiVideo }">
                <VideoPreviewLink v-if="data.import_video__id != 0" :id="data.import_video__id" :aria-label="t('local.preview')">
                    <i class="pi pi-play-circle" />
                </VideoPreviewLink>
            </template>
        </PrColumn>
    </PrDataTable>
</template>

<script setup lang="ts">
import 'primeicons/primeicons.css';
import '@/styles/button.css';
import '@/styles/text.css';

import { FilterMatchMode } from '@primevue/core/api';
import { vLoading } from 'element-plus';
import PrColumn from 'primevue/column';
import PrDataTable from 'primevue/datatable';
import PrListbox from 'primevue/listbox';
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { httpErrorNotification } from '@/components/Notifications';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import DjangoTaskResultStatusBadge from '@/components/widgets/DjangoTaskResultStatusBadge.vue';
import GameLevelIcon from '@/components/widgets/GameLevelIcon.vue';
import { fetchSaoleiImportVideos } from '@/services/accountLinkService';
import type { SaoleiVideo } from '@/utils/accountlinks';
import { DjangoTaskResultStatusOptions } from '@/utils/common/structInterface';
import { MS_Levels } from '@/utils/ms_const';
import { utc_to_local_format } from '@/utils/system/tools';

const props = defineProps({
    saoleiId: {
        type: Number,
        required: true,
    },
});

const filters = ref({
    import_task__status: { value: null, matchMode: FilterMatchMode.EQUALS },
    level: { value: null, matchMode: FilterMatchMode.EQUALS },
});

const tableData = ref<SaoleiVideo[]>([]);
const importing = ref(false);

function refresh() {
    tableData.value.splice(0, tableData.value.length);
    if (!props.saoleiId) return;
    fetchSaoleiImportVideos(props.saoleiId).then((data) => {
        tableData.value = data;
    }).catch(httpErrorNotification);
}

watch(() => props.saoleiId, refresh, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: {
        preview: '预览录像',
    } },
    en: { local: {
        preview: 'Preview video',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style lang="less" scoped>
.el-overlay .p-select-overlay {
    z-index: 3000 !important;
}
</style>
