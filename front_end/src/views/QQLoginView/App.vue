<template>
    <main class="qq-welcome">
        <h1>{{ t('qqLogin.title') }}</h1>
        <p v-if="loading" role="status">
            {{ t('qqLogin.loading') }}
        </p>
        <p v-if="error" class="text-danger" role="alert">
            {{ error }}
        </p>
        <template v-if="status">
            <p v-if="!status.configured" role="status">
                {{ t('qqLogin.errors.not_configured') }}
            </p>
            <div v-if="profile" class="qq-profile">
                <img v-if="profile.avatar_url" :src="profile.avatar_url" width="40" height="40" alt="" referrerpolicy="no-referrer">
                <span>{{ profile.nickname || t('qqLogin.profileUnavailable') }}</span>
            </div>
            <template v-if="status.pending && status.user_id === 0">
                <p>{{ t('qqLogin.distinction') }}</p>
                <p class="text-warning">
                    {{ t('qqLogin.duplicateWarning') }}
                </p>
                <p>{{ t('qqLogin.existingGuide') }}</p>
                <p>{{ t('qqLogin.agreement') }} <a class="link" :href="agreementUrl" target="_blank" rel="noopener noreferrer">{{ t('qqLogin.agreementLink') }}</a></p>
                <div class="qq-actions">
                    <BaseButton :disabled="busy" @click="existingAccount">
                        {{ t('qqLogin.existingAccount') }}
                    </BaseButton>
                    <BaseButton type="primary" :loading="busy" @click="register">
                        {{ t('qqLogin.register') }}
                    </BaseButton>
                </div>
            </template>
            <template v-else-if="status.user_id > 0">
                <p v-if="newAccount" class="text-warning" data-cy="qq-new-account">
                    {{ t('qqLogin.newAccount') }}
                </p>
                <p>{{ t(result === 'linked' ? 'qqLogin.linked' : 'qqLogin.welcome', { username: status.username }) }}</p>
                <div class="qq-actions">
                    <RouterLink class="link" :to="`/player/${status.user_id}/top`">
                        {{ t('qqLogin.openProfile') }}
                    </RouterLink>
                    <RouterLink class="link" :to="`/player/${status.user_id}/accountlink?qq_login=manage`">
                        {{ t('qqLogin.manage') }}
                    </RouterLink>
                </div>
            </template>
            <template v-else>
                <p>{{ t('qqLogin.restartHint') }}</p>
                <QQLoginEntry />
                <RouterLink class="link" to="/login">
                    {{ t('qqLogin.existingAccount') }}
                </RouterLink>
            </template>
        </template>
        <BaseButton v-if="error && !status" @click="load">
            {{ t('button.retry') }}
        </BaseButton>
    </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import BaseButton from '@/components/common/BaseButton.vue';
import QQLoginEntry from '@/components/Login/QQLoginEntry.vue';
import $axios from '@/http';
import { applyLoginSession } from '@/services/loginSession';
import { cancelQQLogin, fetchQQLoginStatus, qqLoginErrorKey, registerQQAccount } from '@/services/qqLoginService';
import type { QQLoginStatus } from '@/services/qqLoginService';

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const status = ref<QQLoginStatus>();
const loading = ref(true);
const busy = ref(false);
const error = ref('');
const result = typeof route.query.result === 'string' ? route.query.result : '';
const newAccount = ref(result === 'registered');
const profile = computed(() => status.value?.pending ?? status.value?.profile);
const agreementUrl = new URL('/agreement.html', new URL($axios.defaults.baseURL ?? '/', window.location.origin)).href;
let active = true;
onBeforeUnmount(() => {
    active = false;
});

async function load() {
    loading.value = true;
    error.value = '';
    try {
        const data = await fetchQQLoginStatus();
        if (active) {
            status.value = data;
            if (result !== '' && !['pending', 'logged_in', 'linked', 'registered'].includes(result)) error.value = t(qqLoginErrorKey(result));
        }
    } catch (err) {
        if (active) error.value = t(qqLoginErrorKey(err));
    } finally {
        if (active) loading.value = false;
    }
}

async function register() {
    if (busy.value) return;
    busy.value = true;
    error.value = '';
    try {
        const user = await registerQQAccount();
        if (!active) return;
        await applyLoginSession(user, $axios);
        if (!active) return;
        newAccount.value = true;
        status.value = undefined;
        await router.replace({ name: 'qq-login', query: { result: 'registered' } });
        await load();
    } catch (err) {
        if (active) {
            status.value = undefined;
            error.value = t(qqLoginErrorKey(err));
        }
    } finally {
        if (active) busy.value = false;
    }
}

async function existingAccount() {
    if (busy.value) return;
    busy.value = true;
    try {
        await cancelQQLogin();
        if (active) await router.replace('/login');
    } catch (err) {
        if (active) error.value = t(qqLoginErrorKey(err));
    } finally {
        if (active) busy.value = false;
    }
}
onMounted(load);
</script>

<style scoped>
.qq-welcome {
    max-width: 42rem;
    margin: 0 auto;
    padding: 1rem;
}
.qq-profile, .qq-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
}
</style>
