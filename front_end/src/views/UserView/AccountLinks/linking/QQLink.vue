<template>
    <form class="account-link-form" data-cy="account-link-form" @submit.prevent="submit">
        <div class="account-link-entry">
            <label>ID <input v-model="identifier" class="account-input" type="text" maxlength="128" inputmode="numeric" :disabled="sending" :aria-label="`${t('platform.q')} ID`"></label>
            <BaseButton native-type="submit" type="primary" :disabled="!valid" :loading="sending">
                {{ t('button.confirm') }}
            </BaseButton>
        </div>
        <p v-if="error" class="text-danger" role="alert">
            {{ error }}
        </p>
        <div class="account-guide">
            <span>
                {{ t('local.QQ') }}
            </span>
        </div>
    </form>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';

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
        QQ: 'QQ号信息网站管理员可见，仅用于展示，不能用于登录本站。QQ 登录需要单独授权绑定。',
    } },
    en: { local: {
        QQ: 'Moderators can see this number. It is for display only and cannot be used to sign in. Authorize QQ login separately.',
    } },
    es: { local: {
        QQ: 'Los moderadores pueden ver este número. Solo sirve para mostrarlo, no para iniciar sesión. Autoriza el acceso con QQ por separado.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
