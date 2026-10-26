<template>
    <slot :open="openDialog" :logout="logout" :labels="{ login: t('local.menu.login'), register: t('common.button.register'), logout: t('local.menu.logout') }" />
    <!-- 以下的所有表单的输入项都需要@keydown.stop，解决horizontal菜单截留空格操作的问题。 -->
    <!-- https://github.com/element-plus/element-plus/issues/10172#issuecomment-1295794523 -->
    <ElDialog v-if="dialogVisible" v-model="dialogVisible" width="min(28rem, 95vw)" append-to-body :title="t(`local.title.${activeDialog}`)">
        <LoginForm v-if="activeDialog === 'login'" @forget-password="activeDialog = 'retrieve'" @login="login" />
        <RegisterForm v-else-if="activeDialog === 'register'" @login="login" />
        <RetrieveForm v-else @login="login" />
    </ElDialog>
</template>

<script lang="ts" setup>
// 认证状态、表单弹窗及提供给导航的操作。
import { ElDialog, ElMessage, ElMessageBox } from 'element-plus';
import { defineAsyncComponent, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import type { LoginControls } from './types';

import { httpErrorNotification } from '@/components/Notifications';
import type { TopAnchors } from '@/services/topRankingService';
import { store } from '@/store';
import type { GetUserInfoResponse } from '@/utils/common/structInterface';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import type { UserProfileData } from '@/utils/userprofile';

const LoginForm = defineAsyncComponent(() => import('./LoginForm.vue'));
const RegisterForm = defineAsyncComponent(() => import('./RegisterForm.vue'));
const RetrieveForm = defineAsyncComponent(() => import('./RetrieveForm.vue'));

const { proxy } = useCurrentInstance();

const dialogVisible = ref(false);
const activeDialog = ref<'login' | 'register' | 'retrieve'>('login');

defineSlots<{ default: (controls: LoginControls) => unknown }>();

function openDialog(form: 'login' | 'register') {
    activeDialog.value = form;
    dialogVisible.value = true;
}

onMounted(async () => {
    // 恢复登录状态时绕过 HTTP 缓存，避免实名等资料修改后读到旧数据。
    await proxy.$axios.get<{ user: GetUserInfoResponse | null; top_anchors: TopAnchors }>('/api/common/loginauto', {
        params: { _t: Date.now() },
    }).then(function (response) {
        store.topAnchors = response.data.top_anchors;
        if (response.data.user) store.login(response.data.user);
        else store.logout();
    }).catch((err: unknown) => {
        store.logout();
        httpErrorNotification(err);
    });
});

const login = (user: UserProfileData) => {
    store.login(user);
    dialogVisible.value = false;
};

let logoutPending = false;

async function logout() {
    if (logoutPending) return;
    logoutPending = true;
    try {
        const confirmed = await ElMessageBox.confirm(t('local.confirmLogout'), t('local.menu.logout'), {
            confirmButtonText: t('common.button.confirm'),
            cancelButtonText: t('common.button.cancel'),
            type: 'warning',
            customStyle: { borderRadius: '0', maxWidth: 'calc(100vw - 24px)' },
        }).then(() => true, () => false);
        if (!confirmed) return;
        await proxy.$axios.post('/userprofile/logout/', {}).then(function () {
            store.logout();
            ElMessage.success({ message: t('common.msg.logoutSuccess'), offset: 68 });
            dialogVisible.value = false;
        }).catch(httpErrorNotification);
    } finally {
        logoutPending = false;
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        confirmLogout: '确定退出当前账号吗？',
        menu: {
            login: '登录',
            logout: '退出',
        },
        title: {
            login: '用户登录',
            register: '用户注册',
            retrieve: '修改密码',
        },
    } },
    en: { local: {
        confirmLogout: 'Log out of the current account?',
        menu: {
            login: 'Login',
            logout: 'Logout',
        },
        title: {
            login: 'Login',
            register: 'Register',
            retrieve: 'Reset Password',
        },
    } },
    de: { local: {
        menu: {
            login: 'Login',
            logout: 'Abmeldem',
            register: 'Registrieren',
        },
    } },
    fr: { local: {
        menu: {
            login: 'Connexion',
        },
        title: {
            register: 'Créer un compte',
        },
    } },
    pl: { local: {
        menu: {
            login: 'login',
            logout: 'wyloguj',
            register: 'zarejestruj się',
        },
        title: {
            login: 'login',
            retrieve: 'resetuj Hasło',
        },
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
