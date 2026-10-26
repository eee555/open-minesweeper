<template>
    <PrColumn field="state" :show-filter-match-modes="false" :show-filter-operator="false" style="width: 0.5em" :show-apply-button="false" :show-clear-button="false">
        <template #body="{data}: {data: VideoAbstract}">
            <VideoStateIcon :state="data.state" />
        </template>
        <template #filter="{ filterModel, filterCallback }">
            <PrListbox v-model="filterModel.value" multiple :options="MS_ServerStates" @change="filterCallback()">
                <template #option="slotProps">
                    <VideoStateIcon :state="slotProps.option" />
                    &nbsp;
                    {{ t(`state.${slotProps.option}`) }}
                </template>
            </PrListbox>
        </template>
    </PrColumn>
</template>

<script setup lang="ts">
import PrColumn from 'primevue/column';
import PrListbox from 'primevue/listbox';
import { useI18n } from 'vue-i18n';

import VideoStateIcon from '@/components/widgets/VideoStateIcon.vue';
import { MS_ServerStates } from '@/utils/ms_const';
import type { VideoAbstract } from '@/utils/videoabstract';

const { t } = useI18n();
</script>
