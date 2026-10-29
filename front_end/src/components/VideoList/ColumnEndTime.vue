<template>
    <PrColumn field="end_time" :sortable="sortable" :header="t('prop.end_time')">
        <template #body="{ data }">
            <span class="text">
                {{ utc_to_local_format(data.end_time) }}
            </span>
        </template>
    </PrColumn>
</template>

<script setup lang="ts">

import PrColumn from 'primevue/column';
import { useI18n } from 'vue-i18n';

import { utc_to_local_format } from '@/utils/system/tools';

defineProps({
    sortable: { type: Boolean, default: false },
});

const { t } = useI18n();
</script>
