<template>
    <div class="account-panel" data-cy="github-panel">
        <p v-if="result" role="status" data-cy="github-result">
            {{ t(`local.result.${result}`) }}
        </p>
        <template v-if="info">
            <dl class="descriptions descriptions-bordered">
                <div class="description-item">
                    <dt>GitHub ID</dt><dd>{{ info.id }}</dd>
                </div>
                <div v-if="profile" class="description-item">
                    <dt>{{ t('local.username') }}</dt><dd><a :href="profile.url" target="_blank" rel="noopener noreferrer">{{ profile.login }}</a></dd>
                </div>
            </dl>
            <p>{{ t('local.profileHint') }}</p>
            <div>
                <BaseButton :disabled="loading" @click="refreshProfile">
                    {{ t('local.refresh') }}
                </BaseButton>
                <BaseButton v-if="owner" :disabled="unlinking" @click="confirmUnlink">
                    {{ t('local.unlink') }}
                </BaseButton>
            </div>
            <p v-if="profileFailed" class="text-danger" role="alert">
                {{ t('local.profileFailed') }}
            </p>
            <p v-if="unlinkFailed" class="text-danger" role="alert">
                {{ t('local.unlinkFailed') }}
            </p>
        </template>
    </div>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import { onBeforeUnmount, ref, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { useActivePanel } from '../useActivePanel';

import BaseButton from '@/components/common/BaseButton.vue';
import { fetchGitHubProfile, unlinkGitHub } from '@/services/githubService';
import type { GitHubPublicProfile } from '@/services/githubService';
import type { AccountGitHub } from '@/utils/accountlinks';

const props = defineProps({
    info: { type: Object as PropType<AccountGitHub | undefined>, default: undefined },
    owner: { type: Boolean, default: false },
    result: { type: String, default: '' },
});
const emit = defineEmits(['refresh']);
const isActive = useActivePanel();
const profile = ref<GitHubPublicProfile>();
const loading = ref(false);
const unlinking = ref(false);
const profileFailed = ref(false);
const unlinkFailed = ref(false);
let controller: AbortController | undefined;

watch(() => props.info?.id, () => {
    controller?.abort(); profile.value = undefined; profileFailed.value = false; unlinkFailed.value = false; loading.value = false;
});
onBeforeUnmount(() => controller?.abort());

async function refreshProfile() {
    if (loading.value || !props.info) return;
    const { id } = props.info;
    controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]);
    loading.value = true;
    profileFailed.value = false;
    try {
        const result = await fetchGitHubProfile(id, signal);
        if (isActive() && id === props.info.id) profile.value = result;
    } catch {
        if (isActive() && id === props.info.id) profileFailed.value = true;
    } finally {
        if (isActive() && id === props.info.id) loading.value = false;
    }
}

async function confirmUnlink() {
    if (unlinking.value || !props.owner || !window.confirm(t('local.confirm'))) return;
    unlinking.value = true;
    unlinkFailed.value = false;
    try {
        await unlinkGitHub();
        if (isActive()) emit('refresh');
    } catch {
        if (isActive()) unlinkFailed.value = true;
    } finally {
        if (isActive()) unlinking.value = false;
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        username: '用户名',
        refresh: '获取／刷新 GitHub 资料',
        unlink: '解除关联',
        profileHint: '公开资料由浏览器直接从 GitHub 获取，不保存到本站。',
        profileFailed: '获取 GitHub 资料失败，请稍后重试。不影响已验证的数字 ID。',
        unlinkFailed: '解除关联失败，请稍后重试。',
        confirm: '解除 GitHub 关联？之后可以重新授权绑定。此操作不会撤销 GitHub 网站中的应用授权。',
        result: {
            linked: 'GitHub 账号关联成功。',
            cancelled: '已取消 GitHub 授权。',
            conflict: '该 GitHub 账号或本站账号已有其他关联，请先解除原关联。',
            expired: '授权已过期或登录状态已变化，请重新开始。',
            remote_failed: 'GitHub 授权失败，请重新尝试。',
            not_configured: 'GitHub 授权暂未配置完成。',
        },
    } },
    en: { local: {
        username: 'Username',
        refresh: 'Load / refresh GitHub profile',
        unlink: 'Unlink account',
        profileHint: 'Your browser loads public profile information directly from GitHub. OpenMS does not store it.',
        profileFailed: 'Could not load GitHub profile data. This does not affect the verified numeric ID.',
        unlinkFailed: 'Could not unlink the account. Please retry later.',
        confirm: 'Unlink GitHub? You can authorize again later. This does not revoke the application authorization on GitHub.',
        result: {
            linked: 'GitHub account linked.',
            cancelled: 'GitHub authorization cancelled.',
            conflict: 'The GitHub or OpenMS account is already linked. Unlink the existing account first.',
            expired: 'Authorization expired or your login session changed. Please start again.',
            remote_failed: 'GitHub authorization failed. Please try again.',
            not_configured: 'GitHub authorization is not configured yet.',
        },
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
