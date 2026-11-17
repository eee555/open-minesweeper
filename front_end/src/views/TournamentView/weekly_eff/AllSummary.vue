<template>
    <BaseTable :empty="rows.length === 0" :column-count="canDisqualify ? 12 : 11" :empty-text="t('ranking.empty')" data-cy="weekly-eff-results">
        <template #head>
            <tr>
                <th scope="col" rowspan="2">
                    {{ t('prop.realName') }}
                </th>
                <th scope="colgroup" colspan="3">
                    {{ t('level.e') }}
                </th>
                <th scope="colgroup" colspan="6">
                    {{ t('level.i') }}
                </th>
                <th scope="col" rowspan="2">
                    {{ t('level.sum') }}
                </th>
                <th v-if="canDisqualify" scope="col" rowspan="2">
                    {{ t('prop.action') }}
                </th>
            </tr>
            <tr>
                <template v-for="group in groups" :key="group.field">
                    <th v-for="index in group.count" :key="index" scope="col">
                        #{{ index }}
                    </th>
                    <th scope="col">
                        {{ t('score.sum') }}
                    </th>
                </template>
            </tr>
        </template>
        <tr v-for="row in rows" :key="row.id" tabindex="0" @click="emit('row-click', row)" @keydown.enter="emit('row-click', row)">
            <td class="table-col-player">
                <PlayerName :user-id="row.user_id" />
            </td>
            <template v-for="group in groups" :key="group.field">
                <td v-for="([id, score], index) in row[group.field]" :key="index" class="table-col-number" @click.stop @keydown.stop>
                    <VideoPreviewLink v-if="id" :id="id">
                        {{ score.toFixed(3) }}
                    </VideoPreviewLink>
                    <span v-else>{{ score.toFixed(3) }}</span>
                </td>
                <td class="table-col-number">
                    {{ (group.field === 'et' ? row.e_sum : row.i_sum).toFixed(3) }}
                </td>
            </template>
            <td class="table-col-number">
                {{ row.score.toFixed(3) }}
            </td>
            <td v-if="canDisqualify" @click.stop @keydown.stop>
                <DisqualifyParticipant :participant="row" @deleted="emit('deleted', $event)" />
            </td>
        </tr>
    </BaseTable>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import DisqualifyParticipant from '../common/DisqualifyParticipant.vue';

import BaseTable from '@/components/common/BaseTable.vue';
import PlayerName from '@/components/PlayerName.vue';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import type { WeeklyEffParticipant } from '@/utils/weeklyEff';

const props = defineProps({
    data: { type: Array<WeeklyEffParticipant>, required: true },
    canDisqualify: { type: Boolean, default: false },
});
const emit = defineEmits<{ 'row-click': [participant: WeeklyEffParticipant]; deleted: [id: number] }>();
const groups = [{ field: 'et', count: 2 }, { field: 'it', count: 5 }] as const;
const rows = computed(() => [...props.data].sort((left, right) => left.score - right.score));
const { t } = useI18n();
</script>
