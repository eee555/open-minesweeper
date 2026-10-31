<template>
    <div>
        {{ t('prop.userId') }}
        <ElInputNumber v-model="userId" :controls="false" :min="1" />
        <BaseButton :loading="loading" @click="loadUser">
            {{ t('button.query') }}
        </BaseButton>
    </div>

    <template v-if="profile">
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
import { ElInput, ElInputNumber } from 'element-plus';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import VCodeBlock from '@/components/common/BaseCodeBlock.vue';
import { actionSuccessNotification, baseErrorNotification, httpErrorNotification } from '@/components/Notifications';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { HIDDEN_NAME } from '@/utils/userprofile';

const { proxy } = useCurrentInstance();

const userId = ref(1);
const loading = ref(false);
const savingUserProfile = ref(false);
const savingUserMS = ref(false);
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
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
