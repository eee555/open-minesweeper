<template>
    <span>
        <a class="link text" :href="gscGuideUrl" target="_blank" rel="noopener noreferrer">
            {{ t('gsc.identifierGuide.guideLink') }}
        </a>
        <div v-if="!participant">
            <BaseButton :disabled="store.isUserAnonymous" :loading="registeringParticipant" @click="registerParticipant">
                {{ t('button.register') }}
            </BaseButton>
            <span v-if="store.isUserAnonymous" class="text-danger">
                {{ t('msg.realNameRequired') }}
            </span>
        </div>
        <div v-else-if="token === ''">
            {{ t('local.registeredPreparing') }}
        </div>
        <div v-else>
            {{ t('gsc.identifierGuide.token') }}
            <span class="ttfamily">{{ token }}</span>
            <IconCopy :text="token" />
            <div v-if="identifier === ''">
                <ElInput v-model="newIdentifier" :placeholder="t('prop.identifier')" style="width: 260px" />
                <BaseButton :loading="registeringIdentifier" @click="registerIdentifier">
                    {{ t('button.register') }}
                </BaseButton>
                <span v-if="errorText !== ''" class="text-danger">
                    {{ errorText }}
                </span>
            </div>
            <div v-else>
                {{ t('gsc.identifierGuide.identifier') }}
                <span class="ttfamily">{{ identifier }}</span>
                <IconCopy :text="identifier" />
            </div>
        </div>
    </span>
</template>

<script setup lang="ts">
import '@/styles/link.css';
import '@/styles/text.css';
import { ElInput } from 'element-plus';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { httpErrorNotification, successNotification, unknownErrorNotification } from '@/components/Notifications';
import IconCopy from '@/components/widgets/IconCopy.vue';
import { store } from '@/store';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { getDocsUrl } from '@/utils/docs';
import type { TournamentParticipant } from '@/utils/tournaments';

const props = defineProps({
    order: { type: Number, default: 0 },
    token: { type: String, default: '' },
});
const emit = defineEmits<{
    refresh: [];
}>();

const identifier = defineModel('identifier', { type: String, default: '' });
const participant = defineModel<TournamentParticipant | null>('participant', { default: null });

const { proxy } = useCurrentInstance();

const errorText = ref<string>('');
const newIdentifier = ref<string>('');
const registeringParticipant = ref(false);
const registeringIdentifier = ref(false);

const gscGuideUrl = getDocsUrl('guide/gsc');

async function registerParticipant() {
    registeringParticipant.value = true;
    await proxy.$axios.post('/api/tournament/gsc/participant', {
        order: props.order,
    }).then((response) => {
        successNotification(response);
        emit('refresh');
    }).catch(httpErrorNotification);
    registeringParticipant.value = false;
}

async function registerIdentifier() {
    if (!props.token) return;
    registeringIdentifier.value = true;
    await proxy.$axios.post('/api/tournament/gsc/participant/identifier', {
        identifier: newIdentifier.value,
        order: props.order,
    }).then((response) => {
        const { data } = response;
        switch (data.type) {
            case 'success':
                successNotification(response);
                identifier.value = newIdentifier.value;
                newIdentifier.value = '';
                emit('refresh');
                break;
            case 'error':
                switch (data.category) {
                    case 'suffix': errorText.value = t('msg.identifierIncorrectSuffix'); break;
                    case 'collision': errorText.value = t('msg.identifierOccupied'); break;
                    case 'invalid': errorText.value = t('msg.identifierIllegal'); break;
                    default: unknownErrorNotification(response);
                }
                break;
            default:
                unknownErrorNotification(response);
        }
    }).catch(httpErrorNotification);
    registeringIdentifier.value = false;
}

const i18nMessages = {
    'zh-cn': { local: {
        registeredPreparing: '已报名，比赛开始后公布比赛标识并开放 Arbiter 标识注册。',
    } },
    en: { local: {
        registeredPreparing: 'Registered. The tournament token and Arbiter identifier registration will be available when the tournament starts.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.ttfamily {
    font-family: 'Courier New', Courier, monospace;
}
</style>
