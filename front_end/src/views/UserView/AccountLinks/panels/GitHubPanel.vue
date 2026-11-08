<template>
    <div class="account-panel" data-cy="github-panel">
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
    </div>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import { onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { useActivePanel } from '../useActivePanel';

import BaseButton from '@/components/common/BaseButton.vue';
import { fetchGitHubProfile, unlinkGitHub } from '@/services/githubService';
import type { GitHubPublicProfile } from '@/services/githubService';
import { AccountGitHub } from '@/utils/accountlinks';

const props = defineProps({ info: { type: AccountGitHub, required: true }, owner: { type: Boolean, default: false } });
const emit = defineEmits(['refresh']);
const isActive = useActivePanel();
const profile = ref<GitHubPublicProfile>();
const loading = ref(false);
const unlinking = ref(false);
const profileFailed = ref(false);
const unlinkFailed = ref(false);
let controller: AbortController | undefined;

watch(() => props.info.id, () => {
    controller?.abort(); profile.value = undefined; profileFailed.value = false; unlinkFailed.value = false; loading.value = false;
});
onBeforeUnmount(() => controller?.abort());

async function refreshProfile() {
    if (loading.value) return;
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
    } },
    en: { local: {
        username: 'Username',
        refresh: 'Load / refresh GitHub profile',
        unlink: 'Unlink account',
        profileHint: 'Your browser loads public profile information directly from GitHub. OpenMS does not store it.',
        profileFailed: 'Could not load GitHub profile data. This does not affect the verified numeric ID.',
        unlinkFailed: 'Could not unlink the account. Please retry later.',
        confirm: 'Unlink GitHub? You can authorize again later. This does not revoke the application authorization on GitHub.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
