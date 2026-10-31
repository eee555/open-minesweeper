<template>
    <ElForm ref="ruleFormRef" :rules="rules" :model="loginForm">
        <!-- 用户名 -->
        <ElFormItem prop="username" :label="t('form.username')">
            <ElInput v-model="loginForm.username" prefix-icon="User" maxlength="20" show-word-limit />
        </ElFormItem>
        <!-- 密码 -->
        <ElFormItem prop="password" :label="t('form.password')" :error="passwordError">
            <ElInput v-model="loginForm.password" maxlength="20" show-password prefix-icon="Lock" />
        </ElFormItem>
        <!-- 验证码 -->
        <ElFormItem prop="captcha" :label="t('form.captcha')" :error="captchaError">
            <div style="display: flex;">
                <ElInput v-model.trim="loginForm.captcha" prefix-icon="Key" class="code" maxlength="4" />
                    &nbsp;
                <ValidCode ref="refValidCode" />
            </div>
        </ElFormItem>
        <!-- 记住我 -->
        <ElFormItem>
            <label class="checkbox rememberMe">
                <input v-model="remember_me" class="checkbox-input" type="checkbox">
                <span>{{ t('local.keepMeLoggedIn') }}</span>
            </label>
            <span :title="t('local.keepMeLoggedInTooltip')">
                <BaseIconInfo class="text" style="margin-left: 0.2rem" />
            </span>
            <div v-if="remember_me" style="margin-left: 0.5rem;">
                <span>{{ t('local.forDays1') }}</span>
                <ElRadioGroup v-model="setExpiry" size="small" style="vertical-align: middle; padding: 0 5px">
                    <ElRadioButton label="1" :value="1" />
                    <ElRadioButton label="7" :value="7" />
                    <ElRadioButton label="30" :value="30" />
                    <ElRadioButton label="90" :value="90" />
                </ElRadioGroup>
                <span>{{ t('local.forDays2') }}</span>
            </div>
        </ElFormItem>
        <ElFormItem>
            <!-- 确认 -->
            <BaseButton type="primary" @click="submitForm(ruleFormRef!)">
                {{ t('local.confirm') }}
            </BaseButton>
            <!-- 忘记密码 -->
            <BaseTextButton
                underline="never" type="primary"
                style="vertical-align: bottom; margin-left: auto" @click="emit('forgetPassword')"
            >
                {{ t('local.forgetPassword') }}
            </BaseTextButton>
        </ElFormItem>
    </ElForm>
    <DiscordAuthorizeButton mode="login" :set-expiry="remember_me ? setExpiry : 0" />
</template>

<script setup lang="ts">
import '@/styles/cards.css';

import type { FormInstance, FormRules } from 'element-plus';
import { ElForm, ElFormItem, ElInput, ElRadioButton, ElRadioGroup } from 'element-plus';
import { onUnmounted, reactive, ref, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseIconInfo from '../common/icons/BaseIconInfo.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import DiscordAuthorizeButton from '@/components/discord/DiscordAuthorizeButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import ValidCode from '@/components/ValidCode.vue';
import useCurrentInstance from '@/utils/common/useCurrentInstance';

const emit = defineEmits(['forgetPassword', 'login']);

const { proxy } = useCurrentInstance();

const refValidCode = useTemplateRef('refValidCode');
const remember_me = ref(false);
const setExpiry = ref(7);
const captchaError = ref('');
const passwordError = ref('');

interface LoginForm {
    username: string;
    password: string;
    captcha: string;
}

const loginForm = reactive<LoginForm>({
    username: '',
    password: '',
    captcha: '',
});

const ruleFormRef = useTemplateRef('ruleFormRef');

const submitForm = async (formEl: FormInstance | undefined) => {
    if (!formEl) return;
    await formEl.validate((valid) => {
        if (!valid) return;
        const user_id = localStorage.getItem('history_user_id');
        proxy.$axios.post('userprofile/login/', {
            user_id: user_id, // 为空时post会自动忽略该项
            username: loginForm.username,
            password: loginForm.password,
            captcha: loginForm.captcha,
            hashkey: refValidCode.value?.hashkey,
            set_expiry: remember_me.value ? setExpiry.value : 0,
        }).then(function ({ data }) {
            if (data.type == 'success') {
                emit('login', data.user);
            } else if (data.type == 'error') {
                if (data.category == 'captcha') {
                    captchaError.value = t('msg.captchaFail');
                } else if (data.category == 'password') {
                    loginForm.captcha = '';
                    passwordError.value = t('msg.usernamePasswordInvalid');
                }
                if (refValidCode.value !== null) refValidCode.value.refreshPic();
            }
        }).catch(httpErrorNotification);
    });
};

onUnmounted(() => {
    if (ruleFormRef.value === null) return;
    ruleFormRef.value.resetFields();
});

const i18nMessages = {
    'zh-cn': { local: {
        confirm: '登录',
        forDays1: '',
        forDays2: '天',
        forgetPassword: '忘记密码',
        keepMeLoggedIn: '记住我',
        keepMeLoggedInTooltip: '连续多天不上线则自动退出登录',
    } },
    en: { local: {
        confirm: 'Log in',
        forDays1: 'for',
        forDays2: 'days',
        forgetPassword: 'Forget password?',
        keepMeLoggedIn: 'Keep me logged in',
        keepMeLoggedInTooltip: 'Automatically log out after a few days of inactivity',
    } },
    de: { local: {
        confirm: 'Login',
        forgetPassword: 'Passwort vergessen?',
        keepMeLoggedIn: 'eingeloggt bleiben',
    } },
    fr: { local: {
        confirm: 'Se connecter',
        forgetPassword: 'Mot de passe oublié ?',
        keepMeLoggedIn: 'Se souvenir de moi',
    } },
    pl: { local: {
        confirm: 'zaloguj',
        forgetPassword: 'zapomniałeś hasła?',
        keepMeLoggedIn: 'utrzym',
    } },
};

const { t } = useI18n({ messages: i18nMessages });

// must be after t is defined
const rules = reactive<FormRules<LoginForm>>({
    username: [{ required: true, message: t('msg.usernameRequired') }],
    password: [{ required: true, message: t('msg.passwordRequired') }],
    captcha: [{ required: true, message: t('msg.captchaRequired') }],
});
</script>
