<template>
    <PrDataTable
        v-if="data.length > 0"
        v-model:filters="filters"
        v-model:expanded-rows="expandedRows"
        filter-display="menu" :value="data" table-layout="auto" data-key="hash"
        :filter-button-props="{
            filter: {
                severity: 'secondary',
                text: true,
                rounded: false,
                size: 'small',
                style: { borderRadius: '0', padding: '0', width: '1rem' }
            }
        }"
        paginator :rows="25" row-hover
        paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown JumpToPageInput CurrentPageReport"
        :rows-per-page-options="[5, 10, 25, 50, 100]"
        @filter="onFilter"
    >
        <PrColumn expander />
        <PrColumn>
            <template #header>
                <label class="checkbox">
                    <input class="checkbox-input" type="checkbox" :checked="!selectedNone && selectedAll" :indeterminate.prop="!selectedAll && !selectedNone" :aria-label="t('local.selectAll')" @change="handleSelectAllChange">
                </label>
            </template>
            <template #body="{data}: {data: UploadEntry}">
                <label class="checkbox">
                    <input class="checkbox-input" type="checkbox" :checked="selectedRows.includes(data)" :aria-label="t('local.selectVideo', { filename: data.file.name })" @change="(event) => handleSelectOneChange(event, data)">
                </label>
            </template>
        </PrColumn>
        <PrColumn field="status" :header="t('prop.status')" :show-filter-match-modes="false" :show-filter-operator="false">
            <template #body="{data}: {data: UploadEntry}">
                {{ t(`local.${data.status}`) }}
            </template>
            <template #filter="{ filterModel, applyFilter }">
                <PrListbox v-model="filterModel.value" :options="[...UploadStatus]" @change="applyFilter()">
                    <template #option="slotProps">
                        {{ t(`local.${slotProps.option}`) }}
                    </template>
                </PrListbox>
            </template>
        </PrColumn>
        <PrColumn field="stat.end_time" :header="t('prop.end_time')" sortable>
            <template #body="{data}: {data: UploadEntry}">
                {{ data.stat ? toISODateTimeString(data.stat.end_time!) : '' }}
            </template>
        </PrColumn>
        <PrColumn field="stat.level" :header="t('prop.level')" :show-filter-match-modes="false" :show-filter-operator="false">
            <template #body="{data}: {data: UploadEntry}">
                {{ data.stat ? formatLevel(data.stat.level) : '' }}
            </template>
            <template #filter="{ filterModel, applyFilter }">
                <PrListbox v-model="filterModel.value" :options="[...MS_Levels]" @change="applyFilter()">
                    <template #option="slotProps">
                        {{ formatLevel(slotProps.option) }}
                    </template>
                </PrListbox>
            </template>
        </PrColumn>
        <PrColumn field="stat.mode" :header="t('prop.mode')" :show-filter-match-modes="false" :show-filter-operator="false">
            <template #body="{data}: {data: UploadEntry}">
                {{ data.stat ? t(`mode.code${data.stat.mode}`) : '' }}
            </template>
            <template #filter="{ filterModel, applyFilter }">
                <PrListbox v-model="filterModel.value" :options="Object.keys(MS_Mode)" @change="applyFilter()">
                    <template #option="slotProps">
                        {{ t(`level.${slotProps.option}`) }}
                    </template>
                </PrListbox>
            </template>
        </PrColumn>
        <PrColumn field="stat.timems" :header="t('prop.time')" sortable>
            <template #body="{data}: {data: UploadEntry}">
                {{ data.stat ? data.stat.displayStat('time') : '' }}
            </template>
        </PrColumn>
        <PrColumn field="stat.bv" :header="t('prop.bv')" sortable />
        <PrColumn field="stat.bvs" :header="t('prop.bvs')" sortable>
            <template #body="{data}: {data: UploadEntry}">
                {{ data.stat ? data.stat.displayStat('bvs') : '' }}
            </template>
        </PrColumn>
        <template #expansion="{data}: {data: UploadEntry}">
            <div class="description-layout">
                <dl class="descriptions">
                    <div class="description-item description-wide">
                        <dt>{{ t('prop.fileName') }}</dt>
                        <dd>
                            {{ data.file.name }}
                        </dd>
                    </div>
                    <template v-if="data.stat">
                        <div class="description-item">
                            <dt>{{ t('prop.cl') }}</dt>
                            <dd>
                                {{ data.stat.displayStat('cl') }}
                            </dd>
                        </div>
                        <div class="description-item description-span-2">
                            <dt>{{ t('prop.ce') }}</dt>
                            <dd>
                                {{ data.stat.displayStat('ce') }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('prop.cl_s') }}</dt>
                            <dd>
                                {{ data.stat.displayStat('cls') }}
                            </dd>
                        </div>
                        <div class="description-item description-span-2">
                            <dt>{{ t('prop.ce_s') }}</dt>
                            <dd>
                                {{ data.stat.displayStat('ces') }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('prop.ioe') }}</dt>
                            <dd>
                                {{ data.stat.displayStat('ioe') }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('prop.thrp') }}</dt>
                            <dd>
                                {{ data.stat.displayStat('thrp') }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('prop.corr') }}</dt>
                            <dd>
                                {{ data.stat.displayStat('corr') }}
                            </dd>
                        </div>
                    </template>
                </dl>
            </div>
        </template>
    </PrDataTable>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import { FilterMatchMode } from '@primevue/core/api';
import PrColumn from 'primevue/column';
import type { DataTableFilterEvent } from 'primevue/datatable';
import PrDataTable from 'primevue/datatable';
import PrListbox from 'primevue/listbox';
import type { PropType } from 'vue';
import { computed, nextTick, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import type { UploadEntry } from './utils';
import { UploadStatus } from './utils';

import { CustomLevel } from '@/utils/customlevel';
import { toISODateTimeString } from '@/utils/datetime';
import { MS_Levels, MS_Mode } from '@/utils/ms_const';

defineProps({
    data: {
        type: Array as PropType<UploadEntry[]>,
        default: () => [],
    },
});

const selectedRows = defineModel<UploadEntry[]>(
    'selected-rows',
    { default: () => [] },
);

const filters = ref({
    status: { value: null, matchMode: FilterMatchMode.EQUALS },
    'stat.level': { value: null, matchMode: FilterMatchMode.EQUALS },
    'stat.mode': { value: null, matchMode: FilterMatchMode.EQUALS },
});

const filteredData = ref<UploadEntry[]>([]);
const expandedRows = ref<UploadEntry[]>([]);

const selectedAll = computed(() => selectedRows.value.length === filteredData.value.length);
const selectedNone = computed(() => selectedRows.value.length === 0);
async function handleSelectAllChange(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    if (!selectedNone.value) {
        selectedRows.value.length = 0;
    } else {
        selectedRows.value = [...filteredData.value];
    }
    // Activation changes the DOM even when the derived checked value stays false.
    await nextTick();
    input.checked = !selectedNone.value && selectedAll.value;
    input.indeterminate = !selectedAll.value && !selectedNone.value;
}

function onFilter(event: DataTableFilterEvent) {
    filteredData.value = event.filteredValue;
}
watch(filteredData, (newVal) => {
    selectedRows.value = selectedRows.value.filter((entry) => newVal.includes(entry));
});

function handleSelectOneChange(event: Event, entry: UploadEntry) {
    if ((event.currentTarget as HTMLInputElement).checked) {
        selectedRows.value.push(entry);
    } else {
        const index = selectedRows.value.indexOf(entry);
        selectedRows.value.splice(index, 1);
    }
}

/* 本地化 Localization */
const i18nMessages = {
    'zh-cn': { local: {
        censorship: '标识未通过',
        collision: '录像已存在',
        custom: '暂不支持此自定义配置',
        fail: '不通过',
        fileext: '无法识别的文件类型',
        filename: '文件名超过了100字节',
        filesize: '文件大小超过了5MB',
        identifier: '新标识',
        incomplete: '游戏未完成',
        mode: '暂不支持此模式',
        needApprove: '需要人工审核',
        parse: '录像解析失败',
        pass: '通过',
        process: '上传中',
        quota: '录像额度已满',
        selectAll: '全选录像',
        selectVideo: '选择录像：{filename}',
        success: '上传成功',
        upload: '上传失败',
    } },
    en: { local: {
        censorship: 'Identifier blocked',
        collision: 'Video already exists',
        custom: 'This custom board is currently not supported',
        fail: 'Fail',
        fileext: 'Invalid file extension',
        filename: 'File name exceeds 100 bytes',
        filesize: 'File size exceeds 5MB',
        identifier: 'New identifier',
        incomplete: 'Game not finished',
        mode: 'Unsupported game mode',
        needApprove: 'Need manual approval',
        parse: 'Cannot parse the file',
        pass: 'Pass',
        process: 'Uploading',
        quota: 'Video quota reached',
        selectAll: 'Select all videos',
        selectVideo: 'Select video: {filename}',
        success: 'Success',
        upload: 'Upload fail',
    } },
};

const { t } = useI18n({ messages: i18nMessages });

function formatLevel(level: string | CustomLevel): string {
    if (level instanceof CustomLevel) {
        return t('level.c', {
            column: level.column,
            mine: level.mine,
            row: level.row,
        });
    }
    return t(`level.${level}`);
}
</script>
