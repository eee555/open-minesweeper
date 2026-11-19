<template>
    <section class="staff-assignment">
        <h1 class="text text-large">
            {{ t('local.staffTitle') }}
        </h1>
        <p v-if="checking" role="status">
            {{ t('local.checking') }}
        </p>
        <template v-else-if="!authorized">
            <p role="alert" class="text-danger" data-cy="staff-assignment-access-error">
                {{ accessError }}
            </p>
            <BaseButton @click="checkAccess">
                {{ t('local.verifyAccess') }}
            </BaseButton>
        </template>
        <fieldset v-else :disabled="working" data-cy="staff-assignment-controls">
            <legend>{{ t('local.staffSettings') }}</legend>
            <label>{{ t('local.siteId') }} <input v-model.number="userId" type="number" min="1" step="1" data-cy="staff-assignment-user-id"></label>
            <BaseButton :disabled="!canSubmit" :loading="working" data-cy="staff-assignment-grant" @click="assignStaff(true)">
                {{ t('local.grant') }}
            </BaseButton>
            <BaseButton :disabled="!canSubmit" :loading="working" data-cy="staff-assignment-revoke" @click="assignStaff(false)">
                {{ t('local.revoke') }}
            </BaseButton>
        </fieldset>
        <p v-if="error" role="alert" class="text-danger" data-cy="staff-assignment-error">
            {{ error }}
        </p>
        <output v-if="result" aria-live="polite" data-cy="staff-assignment-result">{{ t(result.is_staff ? 'local.granted' : 'local.revoked', { id: result.id }) }}</output>
    </section>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import $axios from '@/http';
import { store } from '@/store';

const i18nMessages = {
    'zh-cn': { local: {
        restricted: '仅站长（superuser）可使用此页面，普通管理员无权访问。',
        csrfFailed: '登录权限或 CSRF 校验失败，请重新验证权限。',
        failed: '设置失败，请核对用户 ID 或稍后重试。',
        verifyFailed: '无法验证站长权限，请稍后重试。',
        cannotGrant: '纪念账号不能拥有管理员权限。',
        staffSettings: '设置用户的管理员权限',
        checking: '正在验证站长权限…',
        staffTitle: '站长：管理员权限',
        revoked: '用户 #{id}：已取消管理员权限',
        siteId: '本站用户 ID',
        revoke: '取消管理员权限',
        verifyAccess: '重新验证权限',
        granted: '用户 #{id}：已设为管理员',
        unknownUser: '用户不存在。',
        grant: '设为管理员',
    } },
    en: { local: {
        restricted: 'Only superusers can access this page.',
        csrfFailed: 'Session permissions or CSRF validation failed. Recheck permissions.',
        failed: 'Could not update permissions. Check the user ID or try again later.',
        verifyFailed: 'Could not verify superuser permissions. Try again later.',
        cannotGrant: 'Memorial accounts cannot have staff permissions.',
        staffSettings: 'Set staff permissions for a user',
        checking: 'Checking superuser permissions…',
        staffTitle: 'Superuser: staff permissions',
        revoked: 'User #{id}: staff access revoked',
        siteId: 'Site user ID',
        revoke: 'Revoke staff access',
        verifyAccess: 'Recheck permissions',
        granted: 'User #{id}: staff access granted',
        unknownUser: 'User not found.',
        grant: 'Grant staff access',
    } },
    es: { local: {
        restricted: 'Solo los superusuarios pueden acceder a esta página.',
        csrfFailed: 'Falló la comprobación de permisos de sesión o de CSRF. Vuelve a verificar los permisos.',
        failed: 'No se pudieron actualizar los permisos. Comprueba el ID de usuario o inténtalo más tarde.',
        verifyFailed: 'No se pudieron verificar los permisos de superusuario. Inténtalo de nuevo más tarde.',
        cannotGrant: 'Las cuentas conmemorativas no pueden tener permisos de administración.',
        staffSettings: 'Cambiar permisos de administración de un usuario',
        checking: 'Comprobando permisos de superusuario…',
        staffTitle: 'Superusuario: permisos de administración',
        revoked: 'Usuario n.º {id}: permisos de administración revocados',
        siteId: 'ID de usuario del sitio',
        revoke: 'Revocar permisos de administración',
        verifyAccess: 'Volver a comprobar los permisos',
        granted: 'Usuario n.º {id}: permisos de administración concedidos',
        unknownUser: 'No se encontró el usuario.',
        grant: 'Conceder permisos de administración',
    } },
};
const { t } = useI18n({ messages: i18nMessages });

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
        accessError.value = isAxiosError(reason) && (reason.response?.status === 401 || reason.response?.status === 403) ? t('local.restricted') : t('local.verifyFailed');
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
            accessError.value = t('local.csrfFailed');
        } else {
            error.value = status === 404 ? t('local.unknownUser') : status === 409 ? t('local.cannotGrant') : t('local.failed');
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
