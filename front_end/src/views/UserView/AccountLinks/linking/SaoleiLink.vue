<template>
    <form class="account-link-form" data-cy="account-link-form" @submit.prevent="submit">
        <p class="account-link-recommend" data-cy="saolei-bind-recommend">
            <b>{{ t('local.recommendTitle') }}</b> {{ t('local.recommendBody') }}
        </p>
        <div class="account-link-entry">
            <label>ID <input v-model="identifier" class="account-input" type="text" maxlength="128" inputmode="numeric" :disabled="sending" :aria-label="`${t('platform.c')} ID`"></label>
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
const valid = computed(() => {
    const number = parseInt(identifier.value, 10);
    return number > 0 && number.toString() === identifier.value;
});
function submit() {
    if (valid.value && !props.sending) emit('submit');
}

const i18nMessages = {
    'zh-cn': { local: {
        recommendTitle: '推荐登录扫雷网进行双向绑定。',
        recommendBody: '在扫雷网发起绑定后回到本站确认，即可完成双向关联，录像会按同步设置自动导入。下方手动填写 ID 仅作为兜底，建议优先使用双向绑定。',
        saolei1: '登录',
        saolei2: '，进入个人主页，网址末尾的数字就是ID，如下图所示。',
        title: '手动填写 ID（兜底方式）',
    } },
    en: { local: {
        recommendTitle: 'We recommend signing in to Saolei.wang for two-way linking.',
        recommendBody: 'Start the link on Saolei.wang and confirm it on OpenMS to complete bidirectional linking; your replays will be imported according to your sync settings. Manually entering your ID below is only a fallback, so please use two-way linking when possible.',
        saolei1: 'Go to your profile page on ',
        saolei2: '. The number at the end of your profile URL is your ID, as shown below.',
        title: 'Manually enter your ID (fallback)',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.account-link-recommend {
    box-sizing: border-box;
    max-width: 40rem;
    margin: 0;
    border-left: 3px solid var(--ui-color-primary);
    padding: 6px 10px;
    background: var(--ui-fill-color-light);
    color: var(--ui-text-color-regular);
}
</style>
