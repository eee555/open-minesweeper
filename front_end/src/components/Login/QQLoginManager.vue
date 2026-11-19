<template>
    <section class="qq-login-manager" data-cy="qq-login-manager">
        <h3>{{ t('qqLogin.manage') }}</h3>
        <p>{{ t('qqLogin.distinction') }}</p>
        <p v-if="error" class="text-danger" role="alert">
            {{ error }}
        </p>
        <template v-if="status">
            <p v-if="!status.configured">
                {{ t('qqLogin.errors.not_configured') }}
            </p>
            <div v-if="status.profile" class="qq-profile">
                <img v-if="status.profile.avatar_url" :src="status.profile.avatar_url" width="40" height="40" alt="" referrerpolicy="no-referrer">
                <span>{{ status.profile.nickname || t('qqLogin.profileUnavailable') }}</span>
            </div>
            <p>{{ t(status.linked ? 'qqLogin.linked' : 'qqLogin.unlinked') }}</p>
            <p>{{ t('qqLogin.privateProfile') }}</p>
            <div class="qq-actions">
                <BaseButton :disabled="busy || !status.configured" @click="authorize">
                    {{ t(status.linked ? 'qqLogin.reauthorize' : 'qqLogin.bind') }}
                </BaseButton>
                <BaseButton v-if="status.linked" :disabled="busy || !status.can_unlink" @click="unlink">
                    {{ t('qqLogin.unlink') }}
                </BaseButton>
                <BaseButton :disabled="busy" @click="refresh">
                    {{ t('qqLogin.refresh') }}
                </BaseButton>
            </div>
            <p v-if="status.linked && !status.can_unlink" class="text-warning">
                {{ t('qqLogin.errors.last_login_method') }}
            </p>
            <form v-if="status.can_set_username" class="qq-actions" @submit.prevent="setUsername">
                <label>{{ t('qqLogin.username') }} <input v-model.trim="username" class="account-input" type="text" maxlength="30" required :disabled="busy"></label>
                <BaseButton native-type="submit" :disabled="busy || username === ''">
                    {{ t('qqLogin.setUsername') }}
                </BaseButton>
            </form>
            <p v-if="status.linked && status.has_email">
                {{ t('qqLogin.recoveryReady') }} <RouterLink class="link" to="/login">
                    {{ t('qqLogin.passwordHint') }}
                </RouterLink>
            </p>
            <details v-if="status.linked && !status.has_email">
                <summary>{{ t('qqLogin.bindEmail') }}</summary>
                <ElForm @submit.prevent="bindEmail">
                    <EmailFormItem ref="emailField" v-model="email" check-collision="true" />
                    <EmailCodeBlock ref="emailCodeField" v-model="emailCode" :email="email" :email-state="emailField?.validateState ?? ''" />
                    <BaseButton native-type="submit" :disabled="busy || email === '' || emailCode === ''">
                        {{ t('qqLogin.bindEmail') }}
                    </BaseButton>
                </ElForm>
            </details>
        </template>
        <BaseButton v-else :disabled="busy" @click="refresh">
            {{ t('button.retry') }}
        </BaseButton>
    </section>
</template>

<script setup lang="ts">
import { ElForm } from 'element-plus';
import { onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink } from 'vue-router';

import BaseButton from '@/components/common/BaseButton.vue';
import EmailCodeBlock from '@/components/formItems/EmailCodeBlock.vue';
import EmailFormItem from '@/components/formItems/EmailFormItem.vue';
import $axios from '@/http';
import { applyLoginSession } from '@/services/loginSession';
import { bindQQRecoveryEmail, fetchQQLoginStatus, qqLoginErrorKey, setQQAccountUsername, startQQLogin, unlinkQQLogin } from '@/services/qqLoginService';
import type { QQLoginStatus } from '@/services/qqLoginService';

const { t } = useI18n();
const status = ref<QQLoginStatus>();
const error = ref('');
const busy = ref(false);
const email = ref('');
const emailCode = ref('');
const username = ref('');
const emailField = useTemplateRef('emailField');
const emailCodeField = useTemplateRef<{ readonly hashkey: string }>('emailCodeField');
let active = true;
onBeforeUnmount(() => {
    active = false;
});

async function run(action: () => Promise<void>) {
    if (busy.value) return;
    busy.value = true;
    error.value = '';
    try {
        await action();
    } catch (err) {
        if (active) error.value = t(qqLoginErrorKey(err));
    } finally {
        if (active) busy.value = false;
    }
}
async function load() {
    const data = await fetchQQLoginStatus();
    if (active) status.value = data;
}
async function refresh() {
    await run(load);
}
async function authorize() {
    await run(async () => {
        const url = await startQQLogin('bind');
        if (active) window.location.assign(url);
    });
}
async function unlink() {
    if (!window.confirm(t('qqLogin.confirmUnlink'))) return;
    await run(async () => {
        await unlinkQQLogin(); await load();
    });
}
async function bindEmail() {
    const hashkey = emailCodeField.value?.hashkey;
    if (hashkey === undefined || hashkey === '') return;
    await run(async () => {
        await bindQQRecoveryEmail(email.value, hashkey, emailCode.value); await load();
    });
}
async function setUsername() {
    await run(async () => {
        const user = await setQQAccountUsername(username.value);
        if (active) await applyLoginSession(user, $axios);
        await load();
    });
}
onMounted(refresh);
</script>

<style scoped>
.qq-login-manager {
    border-top: 1px solid var(--el-border-color);
    margin-top: 0.75rem;
    padding-top: 0.5rem;
}
.qq-profile, .qq-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
}
</style>
