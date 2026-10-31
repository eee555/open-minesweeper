<template>
    <BaseCardNormal>
        <BaseTable table-class="pluck-record-table record-table">
            <template #head>
                <tr>
                    <th class="text text-large" scope="col">
                        {{ t('local.pluckRecord') }}
                    </th>
                    <th class="text text-info" scope="col">
                        {{ t('prop.pluck') }}
                    </th>
                </tr>
            </template>
            <tr v-for="level in DensityCustomLevelConfigs" :key="level.code">
                <th class="text text-info" scope="row">
                    {{ customLevelLabel(level) }}
                </th>
                <td class="text">
                    <VideoPreviewLink :id="recordByLevel.get(level.code)?.video_id">
                        {{ recordByLevel.get(level.code)?.pluck.toFixed(6) }}
                    </VideoPreviewLink>
                </td>
            </tr>
        </BaseTable>
    </BaseCardNormal>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import { DensityCustomLevelConfigs } from '@/utils/customlevel';
import type { CustomLevel } from '@/utils/customlevel';

interface PluckRecord {
    level: string;
    video_id: number;
    pluck: number;
}

const props = defineProps({
    records: {
        type: Array as PropType<PluckRecord[]>,
        required: true,
    },
});

const { t } = useI18n({ messages: {
    'zh-cn': { local: {
        pluckRecord: '自定义密度',
    } },
    en: { local: {
        pluckRecord: 'Density',
    } },
} });

const recordByLevel = computed(() => new Map(
    props.records.map((record) => [record.level, record]),
));

function customLevelLabel(customLevel: CustomLevel): string {
    return t('level.c', {
        row: customLevel.row,
        column: customLevel.column,
        mine: customLevel.mine,
    });
}
</script>

<style scoped>
:deep(.record-table) {
    width: 100%;
    table-layout: auto;
}

:deep(.record-table th),
:deep(.record-table td) {
    box-sizing: border-box;
    border: 0;
    border-bottom: 1px solid var(--ui-table-border-color, var(--ui-border-color-lighter));
    padding: 8px 12px;
    text-align: center;
}

:deep(.pluck-record-table th),
:deep(.pluck-record-table td) {
    width: 50%;
}
</style>
