<template>
    <div class="account-link-form" data-cy="github-link">
        <p>{{ t('local.explanation') }}</p>
        <BaseButton :disabled="sending" @click="authorize">
            {{ t('local.authorize') }}
        </BaseButton>
        <p v-if="failed" class="text-danger" role="alert">
            {{ t('local.failed') }}
        </p>
    </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { useActivePanel } from '../useActivePanel';

import BaseButton from '@/components/common/BaseButton.vue';
import { cancelGitHubLink, startGitHubLink } from '@/services/githubService';

const sending = ref(false);
const failed = ref(false);
const isActive = useActivePanel();

async function authorize() {
    if (sending.value) return;
    sending.value = true;
    failed.value = false;
    try {
        const url = await startGitHubLink();
        if (isActive()) window.location.assign(url);
        else {
            const state = new URL(url).searchParams.get('state');
            if (state !== null) await cancelGitHubLink(state);
        }
    } catch {
        if (isActive()) failed.value = true;
    } finally {
        sending.value = false;
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        explanation: '前往 GitHub 授权确认账号归属，关联后公开显示数字 ID。本站不申请邮箱或仓库权限。',
        authorize: '通过 GitHub 关联',
        failed: '无法开始授权，请稍后重试。',
    } },
    en: { local: {
        explanation: 'Authorize on GitHub to verify account ownership. Your numeric ID will be public. No email or repository permissions are requested.',
        authorize: 'Link with GitHub',
        failed: 'Could not start authorization. Please retry later.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
