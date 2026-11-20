<template>
    <BaseButton type="danger" plain :disabled="busy" :aria-label="t('local.disqualify')" :title="t('local.disqualify')" data-cy="disqualify-participant" @click.stop="visible = true">
        <BaseIconDelete />
    </BaseButton>
    <ElDialog v-if="visible" v-model="visible" :title="t('local.disqualify')" width="min(460px, 90vw)" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy" @click.stop>
        <p class="text">
            {{ t('local.confirm') }}
        </p>
        <PlayerName v-if="participant.user_id !== 0" :user-id="participant.user_id" />
        <span v-else>{{ participant.arbiter_identifier__identifier ?? t('anonymous') }}</span>
        <div v-if="task" data-cy="disqualification-status">
            <DjangoTaskResultStatusBadge :status="task.status" />
        </div>
        <p v-if="task?.status === 'FAILED'" class="text-danger" data-cy="disqualification-error">
            {{ t('local.failed') }}
        </p>
        <template #footer>
            <BaseButton :disabled="busy" @click="visible = false">
                {{ t('button.cancel') }}
            </BaseButton>
            <BaseButtonConfirm :loading="busy" @click="submit" />
        </template>
    </ElDialog>
</template>

<script setup lang="ts">
import { ElDialog } from 'element-plus';
import { onScopeDispose, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseButtonConfirm from '@/components/common/BaseButtonConfirm.vue';
import { BaseIconDelete } from '@/components/common/icon';
import { actionSuccessNotification, httpErrorNotification } from '@/components/Notifications';
import PlayerName from '@/components/PlayerName.vue';
import DjangoTaskResultStatusBadge from '@/components/widgets/DjangoTaskResultStatusBadge.vue';
import { disqualifyParticipant, fetchDisqualificationTask } from '@/services/tournamentService';
import type { ParticipantDisqualificationTask } from '@/services/tournamentService';
import { TournamentParticipant } from '@/utils/tournaments';

const props = defineProps({ participant: { type: TournamentParticipant, required: true } });
const emit = defineEmits<{ deleted: [id: number] }>();
const visible = ref(false);
const busy = ref(false);
const task = ref<ParticipantDisqualificationTask>();
let timer: ReturnType<typeof setTimeout> | undefined;
let disposed = false;

function updateTask(value: ParticipantDisqualificationTask) {
    if (disposed) return;
    task.value = value;
    if (value.status === 'SUCCESSFUL') {
        busy.value = false;
        visible.value = false;
        emit('deleted', props.participant.id);
        actionSuccessNotification();
    } else if (value.status === 'FAILED') {
        busy.value = false;
    } else {
        timer = setTimeout(() => {
            void poll(value.id);
        }, 2000);
    }
}

async function poll(id: string) {
    try {
        updateTask(await fetchDisqualificationTask(id));
    } catch (error) {
        if (disposed) return;
        busy.value = false;
        httpErrorNotification(error);
    }
}

async function submit() {
    if (busy.value) return;
    busy.value = true;
    try {
        updateTask(await disqualifyParticipant(props.participant.id));
    } catch (error) {
        if (!disposed) {
            busy.value = false;
            httpErrorNotification(error);
        }
    }
}

onScopeDispose(() => {
    disposed = true;
    clearTimeout(timer);
});

const i18nMessages = {
    'zh-cn': { local: {
        disqualify: '取消比赛资格',
        confirm: '确定取消该选手的比赛资格吗？已发积分将撤回，录像仍会保留。',
        failed: '后台任务失败，请联系管理员查看任务详情。',
    } },
    en: { local: {
        disqualify: 'Disqualify participant',
        confirm: 'Disqualify this participant? Awarded points will be revoked. Replay files will be kept.',
        failed: 'The background task failed. Contact an administrator to inspect it.',
    } },
    es: { local: {
        disqualify: 'Desqualificar participante',
        confirm: '¿Desqualificar a este participante? Los puntos otorgados se revocarán. Los archivos de repetición se conservarán.',
        failed: 'La tarea en segundo plano ha fallado. Contácte al administrador para revisarla.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
