<template>
    <PrColumn :header="t(`prop.${ stat}`)" :sortable="sortable" :sort-field="stat">
        <template #body="{data}: {data: VideoAbstract}">
            <span class="text">{{ data.displayStat(stat) }}</span>
        </template>
    </PrColumn>
</template>

<script setup lang="ts">

import PrColumn from 'primevue/column';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { getStat_stat, VideoAbstract } from '@/utils/videoabstract';

defineProps({
    sortable: { type: Boolean, default: false },
    stat: { type: String as PropType<getStat_stat>, required: true },
});

const { t } = useI18n();
</script>
