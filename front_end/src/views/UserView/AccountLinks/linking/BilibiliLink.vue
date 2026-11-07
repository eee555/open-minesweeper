<template>
    <form class="account-link-form" data-cy="account-link-form" @submit.prevent="submit">
        <div class="account-link-entry">
            <label>ID <input v-model="identifier" class="account-input" type="text" maxlength="128" inputmode="numeric" :disabled="sending" :aria-label="`${t('platform.B')} ID`"></label>
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
                {{ t('local.bilibili1') }}
                <PlatformIcon platform="B" />{{ t('local.bilibili2') }}<br>
                <b class="text-warning">{{ t('local.privacyTitle') }}</b>
                {{ t('local.bilibiliPrivacy') }}
                <img src="@/assets/IdGuideBilibili.png" width="100%">
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
        bilibili1: '进入',
        bilibili2: '个人空间，网址 space.bilibili.com/ 后面的数字就是 UID。',
        bilibiliPrivacy: '本网站账号使用实名展示。关联 Bilibili 后，其他用户可能将你的 Bilibili 账号与你的实名身份联系起来。',
        privacyTitle: '隐私提醒：',
        title: '如何找到ID',
    } },
    en: { local: {
        bilibili1: 'Open your profile on ',
        bilibili2: '. The number after space.bilibili.com/ is your UID.',
        bilibiliPrivacy: 'This site displays accounts under real names. Linking Bilibili may allow others to connect your Bilibili account with your real-name identity.',
        privacyTitle: 'Privacy notice: ',
        title: 'How to locate the ID',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
