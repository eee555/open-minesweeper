<template>
    <ElTable :data="data" :default-sort="{ prop: 'classic_score', order: 'ascending' }" @row-click="handleRowClick">
        <!-- @vue-generic {WeeklyParticipant} -->
        <ElTableColumn :label="t('prop.realName')" sortable>
            <template #default="{row}">
                <PlayerName v-if="row.user_id !== 0" :user-id="row.user_id" />
                <span v-else>{{ t('anonymous') }}</span>
            </template>
        </ElTableColumn>
        <ElTableColumn :label="t('level.e')">
            <!-- @vue-generic {WeeklyParticipant} -->
            <ElTableColumn v-for="index in 2" :key="`e-${index}`" :label="`#${index}`" sortable :sort-method="scoreSort(`classic_et`, index - 1)">
                <template #default="{row}">
                    <VideoPreviewLink v-if="row.classic_et[index - 1][0]" :id="row.classic_et[index - 1][0]">
                        {{ ms_to_s(row.classic_et[index - 1][1]) }}
                    </VideoPreviewLink>
                    <span v-else>{{ ms_to_s(row.classic_et[index - 1][1]) }}</span>
                </template>
            </ElTableColumn>
            <!-- @vue-generic {WeeklyParticipant} -->
            <ElTableColumn prop="classic_e_sum" :label="t('score.sum')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.classic_e_sum) }}
                </template>
            </ElTableColumn>
        </ElTableColumn>
        <ElTableColumn :label="t('level.i')">
            <!-- @vue-generic {WeeklyParticipant} -->
            <ElTableColumn v-for="index in 5" :key="`i-${index}`" :label="`#${index}`" sortable :sort-method="scoreSort(`classic_it`, index - 1)">
                <template #default="{row}">
                    <VideoPreviewLink v-if="row.classic_it[index - 1][0]" :id="row.classic_it[index - 1][0]">
                        {{ ms_to_s(row.classic_it[index - 1][1]) }}
                    </VideoPreviewLink>
                    <span v-else>{{ ms_to_s(row.classic_it[index - 1][1]) }}</span>
                </template>
            </ElTableColumn>
            <!-- @vue-generic {WeeklyParticipant} -->
            <ElTableColumn prop="classic_i_sum" :label="t('score.sum')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.classic_i_sum) }}
                </template>
            </ElTableColumn>
        </ElTableColumn>
        <!-- @vue-generic {WeeklyParticipant} -->
        <ElTableColumn prop="classic_score" :label="t('level.sum')" sortable>
            <template #default="{row}">
                {{ ms_to_s(row.classic_score) }}
            </template>
        </ElTableColumn>
    </ElTable>
</template>

<script setup lang="ts">
import { ElTable, ElTableColumn } from 'element-plus';
import { useI18n } from 'vue-i18n';

import PlayerName from '@/components/PlayerName.vue';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import { ms_to_s } from '@/utils';
import type { WeeklyParticipant } from '@/utils/weekly';

defineProps({
    data: { type: Array<WeeklyParticipant>, default: () => [] },
});

const emit = defineEmits<{
    'row-click': [row: WeeklyParticipant];
}>();

const { t } = useI18n();

function scoreSort(field: 'classic_et' | 'classic_it', index: number) {
    return (left: WeeklyParticipant, right: WeeklyParticipant) => left[field][index][1] - right[field][index][1];
}

function handleRowClick(row: WeeklyParticipant) {
    emit('row-click', row);
}
</script>
