<template>
    <section class="pluck-record">
        <BaseTable table-class="pluck-record-table record-table">
            <template #head>
                <tr>
                    <th scope="col" />
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
    </section>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

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

const { t } = useI18n();

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
.pluck-record {
    min-width: 0;
}

:deep(.record-table th),
:deep(.record-table td) {
    text-align: center;
}

:deep(.pluck-record-table th),
:deep(.pluck-record-table td) {
    width: 50%;
}
</style>
