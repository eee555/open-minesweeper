<template>
    <PrColumn :header="t('prop.file_size')" field="file_size" :sortable="sortable">
        <template #body="{data}: {data: VideoAbstract}">
            {{ data.isLocal ? '—' : data.file_size === 0 ? '-' : formatBytes(data.file_size) }}
        </template>
    </PrColumn>
</template>

<script setup lang="ts">
import PrColumn from 'primevue/column';
import { useI18n } from 'vue-i18n';

import { formatBytes } from '@/utils/strings';
import type { VideoAbstract } from '@/utils/videoabstract';

defineProps({
    sortable: { type: Boolean, default: false },
});

const { t } = useI18n();
</script>
