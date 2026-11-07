<template>
    <form class="account-link-form" data-cy="account-link-form" @submit.prevent="submit">
        <div class="account-link-entry">
            <label>ID <input v-model="identifier" class="account-input" type="text" maxlength="128" inputmode="numeric" :disabled="sending" :aria-label="`${t('platform.w')} ID`"></label>
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
                {{ t('local.wom1') }}
                <PlatformIcon platform="w" />{{ t('local.wom2') }}
                <img src="@/assets/IdGuideWom.png" width="100%">
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
        title: '如何找到ID',
        wom1: '在',
        wom2: '进入你的个人主页，网址结尾的数字就是你的ID。',
    } },
    en: { local: {
        title: 'How to locate the ID',
        wom1: 'Go to your profile page on ',
        wom2: '. The number at the end of the url is your ID.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
