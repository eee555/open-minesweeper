<template>
    <div class="text-large text-regular" data-cy="weekly-eff-personal-total">
        {{ t('level.sum') }}{{ t('punct.colon') }}{{ summary.score.toFixed(3) }}
    </div>
    <BaseTable :column-count="2" :empty="false" data-cy="weekly-eff-personal-summary">
        <template #head>
            <tr>
                <th scope="col">
                    {{ t('level.i') }}
                </th><th scope="col">
                    {{ t('level.e') }}
                </th>
            </tr>
        </template>
        <tr v-for="index in 5" :key="index">
            <td>
                <VideoPreviewLink v-if="summary.it[index - 1][0]" :id="summary.it[index - 1][0]">
                    {{ summary.it[index - 1][1].toFixed(3) }}
                </VideoPreviewLink><span v-else>{{ summary.it[index - 1][1].toFixed(3) }}</span>
            </td>
            <td v-if="index <= 2">
                <VideoPreviewLink v-if="summary.et[index - 1][0]" :id="summary.et[index - 1][0]">
                    {{ summary.et[index - 1][1].toFixed(3) }}
                </VideoPreviewLink><span v-else>{{ summary.et[index - 1][1].toFixed(3) }}</span>
            </td>
            <td v-else>
                {{ t(index === 3 ? 'level.i' : index === 4 ? 'level.e' : 'level.sum') }}{{ t('punct.colon') }}{{ (index === 3 ? summary.i_sum : index === 4 ? summary.e_sum : summary.score).toFixed(3) }}
            </td>
        </tr>
    </BaseTable>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseTable from '@/components/common/BaseTable.vue';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import type { VideoAbstract } from '@/utils/videoabstract';
import { WeeklyEffParticipant } from '@/utils/weeklyEff';

const props = defineProps({ videos: { type: Array<VideoAbstract>, required: true } });
const summary = computed(() => {
    const participant = new WeeklyEffParticipant();
    participant.videos = props.videos;
    return participant;
});
const { t } = useI18n();
</script>
