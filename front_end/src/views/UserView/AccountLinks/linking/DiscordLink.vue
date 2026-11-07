<template>
    <form class="account-link-form" data-cy="account-link-form" @submit.prevent="submit">
        <div class="account-link-entry">
            <label>ID <input v-model="identifier" class="account-input" type="text" maxlength="128" inputmode="numeric" :disabled="sending" :aria-label="`${t('platform.d')} ID`"></label>
            <BaseButton native-type="submit" type="primary" :disabled="!valid" :loading="sending">
                {{ t('button.confirm') }}
            </BaseButton>
        </div>
        <p v-if="error" class="text-danger" role="alert">
            {{ error }}
        </p>
        <div class="account-guide">
            <div class="discord-id-guide">
                <b>{{ t('local.discordTitle') }}</b>
                <p>{{ t('local.discordEnable') }}</p>
                <ul>
                    <li>{{ t('local.discordDesktop') }}</li>
                    <li>{{ t('local.discordMobile') }}</li>
                </ul>
                <p>{{ t('local.discordPaste') }}</p>
                <p class="text-secondary">
                    {{ t('local.discordVerification') }}
                </p>
            </div>
        </div>
    </form>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { isDiscordUserId } from '@/utils/accountlinks';

const props = defineProps({
    sending: { type: Boolean, default: false },
    error: { type: String, default: '' },
});
const emit = defineEmits<{ submit: [] }>();
const identifier = defineModel<string>({ required: true });
const valid = computed(() => isDiscordUserId(identifier.value));
function submit() {
    if (valid.value && !props.sending) emit('submit');
}

const i18nMessages = {
    'zh-cn': { local: {
        discordTitle: '获取自己的 Discord 用户 ID',
        discordEnable: '先在 Discord 的“用户设置 → 高级”中开启“开发者模式”。',
        discordDesktop: '电脑／网页版：在聊天消息或成员列表中找到自己，右键自己的头像 →“复制用户 ID”。',
        discordMobile: '手机端：在聊天消息或成员列表中点自己的头像，打开用户资料 → 右上角“…”→“复制用户 ID”。',
        discordPaste: '将复制的本人数字用户 ID 粘贴到上方 ID 输入框；不要填写用户名、显示名或服务器 ID。',
        discordVerification: '提交后联系管理员审核。关联仅本人和本站管理员可见。',
    } },
    en: { local: {
        discordTitle: 'How to find your own Discord User ID',
        discordEnable: 'Enable Developer Mode in Discord under User Settings → Advanced.',
        discordDesktop: 'Desktop / web: Find yourself in a chat or member list, right-click your own avatar → Copy User ID.',
        discordMobile: 'Mobile: Tap your own avatar in a chat or member list to open your profile → the ⋯ menu in the top-right → Copy User ID.',
        discordPaste: 'Paste your own numeric User ID into the ID field above. Do not enter a username, display name or server ID.',
        discordVerification: 'After submitting, contact a moderator for verification. The link is visible only to you and site moderators.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.discord-id-guide p,
.discord-id-guide ul {
    margin: 0.35rem 0;
}

.discord-id-guide ul {
    padding-left: 1.25rem;
}
</style>
