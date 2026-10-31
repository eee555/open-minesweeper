<template>
    <BaseTable class="top-record-table" :data-nf="nf" :column-count="8">
        <template #head>
            <tr>
                <th scope="col" style="width: 1%">
                    {{ t('prop.level') }}
                </th>
                <th scope="col" style="width: 1%">
                    {{ t('prop.metric') }}
                </th>
                <th scope="col" class="table-col-number">
                    {{ t('local.mean') }}
                </th>
                <th v-for="position in 5" :key="position" scope="col" class="table-col-number">
                    {{ position }}
                </th>
            </tr>
        </template>
        <tr v-for="axis in rows" :key="`${axis.level}${axis.stat}`" :data-field="`${axis.level}${axis.stat}`">
            <th v-if="axis.stat === 't'" rowspan="3" scope="rowgroup">
                {{ t(`level.${axis.level}`) }}
            </th>
            <td>{{ t(`prop.${topStatNames[axis.stat]}`) }}</td>
            <td class="table-col-number">
                <strong>{{ formatTopValue(axis.mean, axis.level, axis.stat) }}</strong>
            </td>
            <td v-for="(video, position) in axis.videos" :key="position" class="table-col-number">
                <VideoPreviewLink v-if="video" :id="video.video_id">
                    {{ formatTopValue(video.value, axis.level, axis.stat) }}
                </VideoPreviewLink>
                <span v-else class="text-secondary">{{ formatTopValue(missingTopValue(axis.stat), axis.level, axis.stat) }}</span>
            </td>
        </tr>
    </BaseTable>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseTable from '@/components/common/BaseTable.vue';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import { formatTopValue, missingTopValue, topAxes, topField, topMean, topStatNames } from '@/services/topRankingService';
import type { TopRecords } from '@/services/topRankingService';

const props = defineProps({
    records: { type: Object as PropType<TopRecords>, required: true },
    nf: { type: Boolean, required: true },
});
const rows = computed(() => topAxes.map((axis) => {
    const record = props.records[topField(props.nf, axis.level, axis.stat)];
    return { ...axis, mean: topMean(record, axis.stat), videos: Array.from({ length: 5 }, (_, position) => record?.videos[position]) };
}));

const i18nMessages = {
    'zh-cn': { local: {
        mean: '均值',
    } },
    en: { local: {
        mean: 'Mean',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.top-record-table {
    margin-top: 8px;
    font-size: var(--ui-font-size-small);
}
.top-record-table th {
    white-space: nowrap;
}
</style>
