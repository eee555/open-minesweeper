<template>
    <form class="account-link-form" data-cy="account-link-form" @submit.prevent="submit">
        <div class="account-link-entry">
            <label>ID <input v-model="identifier" class="account-input" type="text" maxlength="128" inputmode="numeric" :disabled="sending" :aria-label="`${t('platform.a')} ID`"></label>
            <BaseButton native-type="submit" type="primary" :disabled="!valid" :loading="sending">
                {{ t('button.confirm') }}
            </BaseButton>
        </div>
        <p v-if="error" class="text-danger" role="alert">
            {{ error }}
        </p>
        <div class="account-guide">
            <span>
                <b>{{ t('local.title') }}</b><br>
                {{ t('local.msgames1') }}
                <PlatformIcon platform="a" />{{ t('local.msgames2') }}<br>
                <img src="@/assets/IdGuideMsgames1.png" width="100%">
                {{ t('local.msgames3') }}
                <img src="@/assets/IdGuideMsgames2.png" width="100%">
            </span>
        </div>
    </form>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import PlatformIcon from '@/components/widgets/PlatformIcon.vue';

const props = defineProps({
    sending: { type: Boolean, default: false },
    error: { type: String, default: '' },
});
const emit = defineEmits<{ submit: [] }>();
const identifier = defineModel<string>({ required: true });
const valid = computed(() => {
    const number = parseInt(identifier.value, 10);
    return number > 0 && number.toString() === identifier.value;
});
function submit() {
    if (valid.value && !props.sending) emit('submit');
}

const i18nMessages = {
    'zh-cn': { local: {
        msgames1: '在',
        msgames2: '排行榜找到你的位置：',
        msgames3: '在上图点击名字右边的链接，进入如下的个人主页，网址结尾的数字就是ID。',
        title: '如何找到ID',
    } },
    en: { local: {
        msgames1: 'Find yourself on the ',
        msgames2: ' ranking:',
        msgames3: 'Click the link next to your name (see image above) to get to your profile (see image below). The number at the end of the url is your ID.',
        title: 'How to locate the ID',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
