<template>
    <BaseTable v-loading="loading" :empty="participants.length === 0" :column-count="canManage ? 4 : 3" :empty-text="t('ranking.empty')" data-cy="weekly-registered-table">
        <template #head>
            <tr>
                <th scope="col" class="table-col-player">
                    {{ t('prop.realName') }}
                </th>
                <th scope="col" class="registered-interval">
                    {{ t('local.interval') }}
                </th>
                <th scope="col" class="registered-token">
                    {{ t('local.token') }}
                </th>
                <th v-if="canManage" scope="col" class="registered-actions">
                    {{ t('prop.action') }}
                </th>
            </tr>
        </template>
        <tr v-for="row in participants" :key="row.id">
            <td class="table-col-player">
                <PlayerName v-if="row.user_id !== 0" :user-id="row.user_id" />
                <span v-else>{{ t('anonymous') }}</span>
            </td>
            <td class="registered-interval">
                {{ row.start_time ? toISODateTimeString(row.start_time) : '' }} ~ {{ row.end_time ? toISODateTimeString(row.end_time) : '' }}
            </td>
            <td class="registered-token">
                {{ row.token }}
            </td>
            <td v-if="canManage" class="registered-actions">
                <BaseButton
                    v-if="!row.has_videos" type="danger" plain :aria-label="t('local.deleteParticipant')"
                    :disabled="deleting" data-cy="delete-participant" @click="requestDeletion(row)"
                >
                    <BaseIconDelete />
                </BaseButton>
            </td>
        </tr>
    </BaseTable>
    <ElDialog
        v-if="canManage" v-model="dialogVisible" :title="t('local.deleteParticipant')"
        width="min(460px, 90vw)" :close-on-click-modal="!deleting" :close-on-press-escape="!deleting" :show-close="!deleting"
    >
        <p class="text">
            {{ t('local.confirmDeletion') }}
        </p>
        <template v-if="selectedParticipant">
            <PlayerName v-if="selectedParticipant.user_id !== 0" :user-id="selectedParticipant.user_id" />
            <span v-else>{{ t('anonymous') }}</span>
            <div>{{ selectedParticipant.token }}</div>
        </template>
        <template #footer>
            <BaseButton :disabled="deleting" @click="dialogVisible = false">
                {{ t('button.cancel') }}
            </BaseButton>
            <BaseButtonConfirm :loading="deleting" @click="confirmDeletion" />
        </template>
    </ElDialog>
</template>

<script setup lang="ts">
import { ElDialog, vLoading } from 'element-plus';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseButtonConfirm from '@/components/common/BaseButtonConfirm.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { BaseIconDelete } from '@/components/common/icon';
import { actionSuccessNotification, httpErrorNotification } from '@/components/Notifications';
import PlayerName from '@/components/PlayerName.vue';
import { deleteParticipant } from '@/services/tournamentService';
import { toISODateTimeString } from '@/utils/datetime';
import type { TournamentParticipant } from '@/utils/tournaments';

const props = defineProps({
    participants: { type: Array<TournamentParticipant>, required: true },
    canManage: { type: Boolean, required: true },
    loading: { type: Boolean, default: false },
});
const emit = defineEmits<{
    deleted: [participantId: number];
}>();
const dialogVisible = ref(false);
const selectedParticipant = ref<TournamentParticipant>();
const deleting = ref(false);

function requestDeletion(participant: TournamentParticipant) {
    selectedParticipant.value = participant;
    dialogVisible.value = true;
}

async function confirmDeletion() {
    if (!props.canManage || !selectedParticipant.value || deleting.value) return;
    const participantId = selectedParticipant.value.id;
    deleting.value = true;
    try {
        await deleteParticipant(participantId);
        emit('deleted', participantId);
        dialogVisible.value = false;
        actionSuccessNotification();
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        deleting.value = false;
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        interval: '参赛时间区间',
        token: '比赛标识',
        deleteParticipant: '删除参赛者',
        confirmDeletion: '确定删除该参赛者吗？',
    } },
    en: { local: {
        interval: 'Session interval',
        token: 'Tournament token',
        deleteParticipant: 'Delete participant',
        confirmDeletion: 'Delete this participant?',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.table-col-player {
    min-width: 150px;
}

.registered-interval {
    min-width: 330px;
    white-space: nowrap;
}

.registered-token {
    min-width: 180px;
}

.registered-actions {
    width: 90px;
    min-width: 90px;
}
</style>
