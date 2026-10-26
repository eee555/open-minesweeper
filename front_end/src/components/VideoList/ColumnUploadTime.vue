<template>
    <PrColumn field="upload_time" :sortable="sortable" :header="t('prop.upload_time')" style="min-width: 11em">
        <template #body="{ data }">
            <span class="text">
                {{ data.isLocal ? '—' : utc_to_local_format(data.upload_time) }}
            </span>
        </template>
    </PrColumn>
</template>

<script setup lang="ts">
import '@/styles/text.css';

import PrColumn from 'primevue/column';
import { useI18n } from 'vue-i18n';

import { utc_to_local_format } from '@/utils/system/tools';

defineProps({
    sortable: { type: Boolean, default: false },
});

const { t } = useI18n();
</script>
