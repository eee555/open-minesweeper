<template>
    <div>
        {{ t('prop.userId') }}
        <ElInputNumber v-model="userId" :controls="false" :min="1" />
        <BaseButton :loading="loading" @click="loadUser">
            {{ t('button.query') }}
        </BaseButton>
    </div>

    <template v-if="profile">
        <div>
            {{ t('local.verifiedState') }}{{ t('punct.colon') }}{{ profile.verified === true ? t('local.verified') : t('local.unverified') }}
            <BaseButton :loading="verifying" data-cy="staff-grant-verification" @click="submitVerification('grant')">
                {{ t('local.grantVerification') }}
            </BaseButton>
            <BaseButton v-if="store.user.is_superuser" type="danger" :loading="verifying" data-cy="staff-revoke-verification" @click="submitVerification('revoke')">
                {{ t('local.revokeVerification') }}
            </BaseButton>
            <span v-if="verificationTaskText" role="status" data-cy="staff-verification-task">{{ verificationTaskText }}</span>
        </div>
        <VCodeBlock :code="JSON.stringify(profile, null, 2)" lang="json" />
        {{ t('local.userProfile') }}
        <ElInput v-model="userProfileRequestBody" type="textarea" :autosize="{ minRows: 8 }" data-cy="staff-profile-json" />
        <BaseButton type="primary" :loading="savingUserProfile" data-cy="staff-save-profile" @click="saveUserProfile">
            {{ t('local.patchUserProfile') }}
        </BaseButton>
        {{ t('local.userMS') }}
        <ElInput v-model="userMSRequestBody" type="textarea" :autosize="{ minRows: 8 }" />
        <BaseButton type="primary" :loading="savingUserMS" @click="saveUserMS">
            {{ t('local.patchUserMS') }}
        </BaseButton>
    </template>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { ElInput, ElInputNumber } from 'element-plus';
import { onUnmounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import VCodeBlock from '@/components/common/BaseCodeBlock.vue';
import { actionSuccessNotification, baseErrorNotification, generalErrorNotification, httpErrorNotification } from '@/components/Notifications';
import { fetchVerificationTask, grantVerification, revokeVerification } from '@/services/playerVerificationService';
import { store } from '@/store';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { HIDDEN_NAME } from '@/utils/userprofile';

const { proxy } = useCurrentInstance();

const userId = ref(1);
const loading = ref(false);
const savingUserProfile = ref(false);
const savingUserMS = ref(false);
const verifying = ref(false);
const verificationTaskText = ref('');
let verificationTimer: ReturnType<typeof setInterval> | undefined;
const profile = ref<Record<string, unknown> | null>(null);
const loadedUserId = ref<number | null>(null);
const userProfileRequestBody = ref('{}');
const userMSRequestBody = ref('{}');

async function reloadUser(id: number) {
    await proxy.$axios.get<Record<string, unknown>>(`/api/userprofile/admin/detail/${id}`).then((response) => {
        profile.value = response.data;
        loadedUserId.value = id;
    });
}

async function loadUser() {
    loading.value = true;
    await reloadUser(userId.value).then(() => {
        userProfileRequestBody.value = '{}';
        userMSRequestBody.value = '{}';
    }).catch(httpErrorNotification);
    loading.value = false;
}

function parseRequestBody(body: string) {
    try {
        const data: unknown = JSON.parse(body);
        if (typeof data !== 'object' || data === null || Array.isArray(data)) {
            baseErrorNotification(t('local.jsonError'), t('local.jsonObjectRequired'));
            return null;
        }
        return data as Record<string, unknown>;
    } catch (error) {
        baseErrorNotification(t('local.jsonError'), String(error));
        return null;
    }
}

async function saveUserProfile() {
    if (!profile.value || loadedUserId.value === null) return;

    const payload = parseRequestBody(userProfileRequestBody.value);
    if (payload === null) return;
    if (['realname', 'firstname', 'lastname'].some((field) => {
        const value = payload[field];
        return typeof value === 'string' && value.trim() === HIDDEN_NAME;
    })) {
        baseErrorNotification(t('local.jsonError'), t('msg.reservedName'));
        return;
    }
    if (profile.value.can_hide_realname === true && payload.can_hide_realname === false && !window.confirm(t('local.revokePrivacy'))) return;

    savingUserProfile.value = true;
    await proxy.$axios.patch<Record<string, unknown>>(`/api/userprofile/admin/update/${loadedUserId.value}`, payload).then((response) => {
        profile.value = response.data;
        userProfileRequestBody.value = '{}';
        actionSuccessNotification();
    }).catch(httpErrorNotification);
    savingUserProfile.value = false;
}

async function checkVerificationTask(targetId: number, taskId: string): Promise<void> {
    try {
        const result = await fetchVerificationTask(taskId);
        if (result.status === 'READY' || result.status === 'RUNNING') return;
        if (verificationTimer !== undefined) clearInterval(verificationTimer);
        verificationTimer = undefined;
        const applied = result.status === 'SUCCESSFUL' && result.result?.status === 'applied';
        verificationTaskText.value = applied ? t('local.verificationDone') : t('local.verificationConflict');
        if (applied) actionSuccessNotification();
        await reloadUser(targetId);
    } catch (error) {
        if (verificationTimer !== undefined) clearInterval(verificationTimer);
        verificationTimer = undefined;
        verificationTaskText.value = t('local.verificationConflict');
        httpErrorNotification(error);
    }
}

async function submitVerification(operation: 'grant' | 'revoke') {
    if (loadedUserId.value === null) return;
    if (!window.confirm(t(operation === 'grant' ? 'local.grantConfirm' : 'local.revokeConfirm', { id: loadedUserId.value }))) return;
    const id = loadedUserId.value;
    verifying.value = true;
    try {
        const task = operation === 'grant' ? await grantVerification(id) : await revokeVerification(id);
        verificationTaskText.value = t('local.verificationQueued', { id: task.task_id });
        if (verificationTimer !== undefined) clearInterval(verificationTimer);
        verificationTimer = setInterval(() => {
            void checkVerificationTask(id, task.task_id);
        }, 1000);
    } catch (error) {
        if (isAxiosError<{ object?: string; category?: string }>(error) && error.response?.data?.object === 'verification') {
            generalErrorNotification('verification', error.response.data.category ?? 'not_found');
        } else {
            httpErrorNotification(error);
        }
    }
    verifying.value = false;
}

onUnmounted(() => {
    if (verificationTimer !== undefined) clearInterval(verificationTimer);
});

async function saveUserMS() {
    if (!profile.value || loadedUserId.value === null) return;

    const payload = parseRequestBody(userMSRequestBody.value);
    if (payload === null) return;

    const usermsId = profile.value.userms_id;
    if (typeof usermsId !== 'number') {
        baseErrorNotification(t('local.userMSError'), t('local.missingUserMS'));
        return;
    }

    const id = loadedUserId.value;
    savingUserMS.value = true;
    await proxy.$axios.patch<Record<string, unknown>>(`/api/msuser/admin/update/${usermsId}`, payload).then(async () => {
        userMSRequestBody.value = '{}';
        await reloadUser(id);
        actionSuccessNotification();
    }).catch(httpErrorNotification);
    savingUserMS.value = false;
}

const i18nMessages = {
    'zh-cn': { local: {
        userProfile: '用户资料（UserProfile）',
        userMS: '扫雷数据（UserMS）',
        patchUserProfile: 'PATCH UserProfile（修改用户资料）',
        patchUserMS: 'PATCH UserMS（修改扫雷数据）',
        jsonError: 'JSON错误',
        jsonObjectRequired: '请求体必须是 JSON 对象',
        userMSError: 'UserMS错误',
        missingUserMS: '当前用户没有可用的 userms_id',
        revokePrivacy: '撤销隐藏实名资格后，将关闭隐藏，实名会在缓存正常更新后恢复公开。是否继续？',
        verifiedState: '玩家认证状态',
        verified: '已认证',
        unverified: '未认证',
        grantVerification: '主动认证该用户',
        revokeVerification: '取消该用户认证',
        grantConfirm: '确定将用户 #{id} 设为已认证根节点吗？已有申请或入边会被覆盖。',
        revokeConfirm: '确定取消用户 #{id} 的认证吗？其有效后代也会失去本站认证。',
        verificationQueued: '认证任务已受理：{id}',
        verificationDone: '认证任务已完成。',
        verificationConflict: '认证任务未生效，请刷新后重试。',
    } },
    en: { local: {
        userProfile: 'User profile (UserProfile)',
        userMS: 'Minesweeper data (UserMS)',
        patchUserProfile: 'PATCH UserProfile (Update user profile)',
        patchUserMS: 'PATCH UserMS (Update Minesweeper data)',
        jsonError: 'JSON error',
        jsonObjectRequired: 'The request body must be a JSON object',
        userMSError: 'UserMS error',
        missingUserMS: 'This user has no available userms_id',
        revokePrivacy: 'Revoking eligibility also turns off hiding. Names become public after normal cache updates. Continue?',
        verifiedState: 'Player verification',
        verified: 'Verified',
        unverified: 'Not verified',
        grantVerification: 'Verify this user',
        revokeVerification: 'Revoke verification',
        grantConfirm: 'Make user #{id} a verified root? An existing request or edge will be overwritten.',
        revokeConfirm: 'Revoke verification for user #{id}? Effective descendants also lose site verification.',
        verificationQueued: 'Verification task accepted: {id}',
        verificationDone: 'Verification task completed.',
        verificationConflict: 'The verification task did not apply. Refresh and try again.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
