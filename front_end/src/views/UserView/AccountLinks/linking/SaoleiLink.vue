<template>
    <form class="account-link-form" data-cy="account-link-form" @submit.prevent="submit">
        <div class="account-link-entry">
            <label>ID <input v-model="identifier" class="account-input" type="text" maxlength="128" inputmode="numeric" :disabled="sending" :aria-label="`${t('platform.c')} ID`"></label>
            <BaseButton native-type="submit" type="primary" :disabled="!valid" :loading="sending">
                {{ t('button.confirm') }}
            </BaseButton>
        </div>
        <div class="account-guide account-sync-preferences" data-cy="saolei-sync-preferences">
            <label class="checkbox">
                <input v-model="syncFromSaolei" class="checkbox-input" type="checkbox" :disabled="sending">
                <span>{{ t('local.syncFromSaolei') }}</span>
            </label>
            <label class="checkbox">
                <input v-model="syncToSaolei" class="checkbox-input" type="checkbox" :disabled="sending">
                <span>{{ t('local.syncToSaolei') }}</span>
            </label>
        </div>
        <p v-if="error" class="text-danger" role="alert">
            {{ error }}
        </p>
        <div class="account-guide">
            <span>
                <b>{{ t('local.title') }}</b><br>
                {{ t('local.saolei1') }}
                <PlatformIcon platform="c" />{{ t('local.saolei2') }}<br>
                <img src="@/assets/IdGuideSaolei.png" width="100%">
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
// 同步偏好勾选（默认全部同意），由父组件在提交时随 create 请求携带
const syncFromSaolei = defineModel<boolean>('syncFromSaolei', { default: true });
const syncToSaolei = defineModel<boolean>('syncToSaolei', { default: true });
const valid = computed(() => {
    const number = parseInt(identifier.value, 10);
    return number > 0 && number.toString() === identifier.value;
});
function submit() {
    if (valid.value && !props.sending) emit('submit');
}

const i18nMessages = {
    'zh-cn': { local: {
        saolei1: '登录',
        saolei2: '，进入个人主页，网址末尾的数字就是ID，如下图所示。',
        title: '如何找到ID',
        syncFromSaolei: '扫雷网上传录像自动同步开源网',
        syncToSaolei: '开源网上传录像自动同步扫雷网',
    } },
    en: { local: {
        saolei1: 'Go to your profile page on ',
        saolei2: '. The number at the end of your profile URL is your ID, as shown below.',
        title: 'How to locate the ID',
        syncFromSaolei: 'Automatically sync replays uploaded on Saolei.wang to this site',
        syncToSaolei: 'Automatically sync replays uploaded here to Saolei.wang',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
