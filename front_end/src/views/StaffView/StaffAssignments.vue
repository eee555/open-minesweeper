<template>
    <section class="staff-assignment">
        <h1 class="text text-large">
            站长：管理员权限
        </h1>
        <p v-if="checking" role="status">
            正在验证站长权限…
        </p>
        <template v-else-if="!authorized">
            <p role="alert" class="text-danger" data-cy="staff-assignment-access-error">
                {{ accessError }}
            </p>
            <BaseButton @click="checkAccess">
                重新验证权限
            </BaseButton>
        </template>
        <fieldset v-else :disabled="working" data-cy="staff-assignment-controls">
            <legend>设置用户的管理员权限</legend>
            <label>本站用户 ID <input v-model.number="userId" type="number" min="1" step="1" data-cy="staff-assignment-user-id"></label>
            <BaseButton :disabled="!canSubmit" :loading="working" data-cy="staff-assignment-grant" @click="assignStaff(true)">
                设为管理员
            </BaseButton>
            <BaseButton :disabled="!canSubmit" :loading="working" data-cy="staff-assignment-revoke" @click="assignStaff(false)">
                取消管理员权限
            </BaseButton>
        </fieldset>
        <p v-if="error" role="alert" class="text-danger" data-cy="staff-assignment-error">
            {{ error }}
        </p>
        <output v-if="result" aria-live="polite" data-cy="staff-assignment-result">用户 #{{ result.id }}：{{ result.is_staff ? '已设为管理员' : '已取消管理员权限' }}</output>
    </section>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { computed, onMounted, ref, watch } from 'vue';

import BaseButton from '@/components/common/BaseButton.vue';
import $axios from '@/http';
import { store } from '@/store';
import '@/styles/text.css';

interface StaffAssignment {
    id: number;
    is_staff: boolean;
}

const endpoint = '/api/userprofile/admin/staff';
const checking = ref(true);
const authorized = ref(false);
const accessError = ref('');
const csrfToken = ref('');
const userId = ref<number | string>('');
const working = ref(false);
const result = ref<StaffAssignment>();
const error = ref('');
const canSubmit = computed(() => authorized.value && !working.value && typeof userId.value === 'number' && Number.isSafeInteger(userId.value) && userId.value > 0);

watch(userId, () => {
    result.value = undefined;
    error.value = '';
});
onMounted(checkAccess);

async function checkAccess() {
    checking.value = true;
    authorized.value = false;
    try {
        const { data } = await $axios.get<{ csrf_token: string }>(endpoint);
        csrfToken.value = data.csrf_token;
        authorized.value = true;
        accessError.value = '';
    } catch (reason) {
        accessError.value = isAxiosError(reason) && (reason.response?.status === 401 || reason.response?.status === 403) ? '仅站长（superuser）可使用此页面，普通管理员无权访问。' : '无法验证站长权限，请稍后重试。';
    } finally {
        checking.value = false;
    }
}

async function assignStaff(isStaff: boolean) {
    if (!canSubmit.value || typeof userId.value !== 'number') return;
    const id = userId.value;
    working.value = true;
    result.value = undefined;
    error.value = '';
    try {
        const { data } = await $axios.post<StaffAssignment>(endpoint, { user_id: id, is_staff: isStaff }, { headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken.value } });
        result.value = data;
        if (store.user.id === data.id) store.user.is_staff = data.is_staff;
    } catch (reason) {
        const status = isAxiosError(reason) ? reason.response?.status : undefined;
        if (status === 401 || status === 403) {
            authorized.value = false;
            accessError.value = '登录权限或 CSRF 校验失败，请重新验证权限。';
        } else {
            error.value = status === 404 ? '用户不存在。' : status === 409 ? '纪念账号不能拥有管理员权限。' : '设置失败，请核对用户 ID 或稍后重试。';
        }
    } finally {
        working.value = false;
    }
}
</script>

<style scoped>
.staff-assignment {
    display: grid;
    gap: 8px;
}
fieldset {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    border: 1px solid var(--el-border-color);
}
input {
    color: var(--el-text-color-primary);
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color);
    border-radius: 0;
}
</style>
