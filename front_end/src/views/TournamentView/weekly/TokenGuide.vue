<template>
    <span>
        <a class="link text" :href="weeklyGuideUrl" target="_blank" rel="noopener noreferrer">
            {{ t('gsc.identifierGuide.guideLink') }}
        </a>
        <div v-if="token === '' && !registrationOpen">
            {{ t('gsc.identifierGuide.preparing') }}
        </div>
        <div v-else-if="token === ''">
            <BaseButton :disabled="store.isUserAnonymous" :loading="registeringParticipant" @click="registerDialogVisible = true">
                {{ t('local.register') }}
            </BaseButton>
            <span v-if="store.isUserAnonymous" class="text-danger">
                {{ t('msg.realNameRequired') }}
            </span>
            <ElDialog v-model="registerDialogVisible">
                <template #header>
                    {{ t('local.registerHeader') }}
                </template>
                {{ t('local.registerConfirm') }}
                <template #footer>
                    <BaseButton @click="registerDialogVisible = false">
                        {{ t('local.registerCancel') }}
                    </BaseButton>
                    <BaseButtonConfirm @click="registerParticipant" />
                </template>
            </ElDialog>
        </div>
        <div v-else>
            {{ t('gsc.identifierGuide.token') }}
            <span class="ttfamily">{{ token }}</span>
            <IconCopy :text="token" />
            <div data-cy="weekly-participant-window">
                {{ t('local.deadline') }}{{ t('punct.colon') }}
                {{ displayTime(participant?.start_time) }}
                &nbsp;~&nbsp;
                {{ displayTime(participant?.end_time) }}
            </div>
        </div>
    </span>
</template>

<script setup lang="ts">
import '@/styles/link.css';
import '@/styles/text.css';
import { ElDialog } from 'element-plus';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseButtonConfirm from '@/components/common/BaseButtonConfirm.vue';
import { actionSuccessNotification, httpErrorNotification } from '@/components/Notifications';
import IconCopy from '@/components/widgets/IconCopy.vue';
import { createWeeklyParticipant } from '@/services/tournamentService';
import { store } from '@/store';
import { toDate, toISODateTimeString } from '@/utils/datetime';
import { getDocsUrl } from '@/utils/docs';
import type { WeeklyParticipant } from '@/utils/weekly';

const props = defineProps({
    tournamentId: { type: Number, required: true },
    registrationOpen: { type: Boolean },
    participant: {
        type: Object as () => WeeklyParticipant | null,
        default: null,
    },
});
const emit = defineEmits<{
    registered: [participant: WeeklyParticipant];
}>();

const token = defineModel('token', { type: String, default: '' });

const registeringParticipant = ref(false);
const registerDialogVisible = ref(false);

const weeklyGuideUrl = getDocsUrl('guide/weekly-tournament');

async function registerParticipant() {
    registeringParticipant.value = true;
    await createWeeklyParticipant(props.tournamentId).then((participant) => {
        actionSuccessNotification();
        token.value = participant.token;
        emit('registered', participant);
    }).catch(httpErrorNotification);
    registerDialogVisible.value = false;
    registeringParticipant.value = false;
}

function displayTime(time: string | Date | null | undefined) {
    const date = toDate(time);
    return date ? toISODateTimeString(date) : '';
}

const i18nMessages = {
    'zh-cn': { local: {
        deadline: '有效时间',
        register: '开始打卡',
        registerCancel: '我还没准备好',
        registerConfirm: '操作不可撤回，确定开始参赛吗？你从现在开始将有两小时上传比赛录像。',
        registerHeader: '准备好了吗？',
    } },
    en: { local: {
        deadline: 'Session interval',
        register: 'Start my session',
        registerCancel: 'I am not ready',
        registerConfirm: 'This action is irreversible. Are you sure you want to start your session? You will have 2 hours to upload your videos.',
        registerHeader: 'Are you ready?',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.ttfamily {
    font-family: 'Courier New', Courier, monospace;
}
</style>
