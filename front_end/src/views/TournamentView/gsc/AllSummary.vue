<template>
    <!-- @vue-generic {GSCParticipant} -->
    <ElTable :data="data" :default-sort="{ prop: 'sum_tsum', order: 'ascending' }" @row-click="handleRowClick">
        <ElTableColumn prop="user_id" sortable>
            <template #default="{row}">
                <PlayerName v-if="row.user_id !== 0" :user-id="row.user_id" />
                <span v-else>{{ row.arbiter_identifier__identifier }}</span>
            </template>
        </ElTableColumn>
        <ElTableColumn :label="t('level.b')">
            <ElTableColumn prop="bt1st" :label="t('score.best')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.bt1st) }}
                </template>
            </ElTableColumn>
            <ElTableColumn prop="bt20th" :label="t('score.edge')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.bt20th) }}
                </template>
            </ElTableColumn>
            <ElTableColumn prop="bt20sum" :label="t('score.sum')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.bt20sum) }}
                </template>
            </ElTableColumn>
        </ElTableColumn>
        <ElTableColumn :label="t('level.i')">
            <ElTableColumn prop="it1st" :label="t('score.best')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.it1st) }}
                </template>
            </ElTableColumn>
            <ElTableColumn prop="it12th" :label="t('score.edge')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.it12th) }}
                </template>
            </ElTableColumn>
            <ElTableColumn prop="it12sum" :label="t('score.sum')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.it12sum) }}
                </template>
            </ElTableColumn>
        </ElTableColumn>
        <ElTableColumn :label="t('level.e')">
            <ElTableColumn prop="et1st" :label="t('score.best')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.et1st) }}
                </template>
            </ElTableColumn>
            <ElTableColumn prop="et5th" :label="t('score.edge')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.et5th) }}
                </template>
            </ElTableColumn>
            <ElTableColumn prop="et5sum" :label="t('score.sum')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.et5sum) }}
                </template>
            </ElTableColumn>
        </ElTableColumn>
        <ElTableColumn :label="t('level.sum')">
            <ElTableColumn prop="sum_tbest" :label="t('score.best')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.sum_tbest) }}
                </template>
            </ElTableColumn>
            <ElTableColumn prop="sum_tedge" :label="t('score.edge')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.sum_tedge) }}
                </template>
            </ElTableColumn>
            <ElTableColumn prop="sum_tsum" :label="t('score.sum')" sortable>
                <template #default="{row}">
                    {{ ms_to_s(row.sum_tsum) }}
                </template>
            </ElTableColumn>
        </ElTableColumn>
    </ElTable>
</template>

<script setup lang="ts">
import { ElTable, ElTableColumn } from 'element-plus';
import { useI18n } from 'vue-i18n';

import PlayerName from '@/components/PlayerName.vue';
import { ms_to_s } from '@/utils';
import type { GSCParticipant } from '@/utils/gsc';

defineProps({
    data: {
        type: Array<GSCParticipant>,
        default: () => [],
    },
});

const emit = defineEmits(['row-click']);

const { t } = useI18n();

function handleRowClick(row: GSCParticipant) {
    emit('row-click', row);
}
</script>
