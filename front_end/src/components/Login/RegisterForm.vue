<template>
    <ElForm ref="ruleFormRef" :model="registerForm" status-icon>
        <!-- 用户名 -->
        <ElFormItem ref="usernameFormRef" prop="username" data-cy="usernameFormItem">
            <template #label>
                {{ t('form.username') }}
            </template>
            <ElInput
                v-model="registerForm.username" prefix-icon="User" maxlength="20" show-word-limit
                @input="usernameInputHandler" @change="usernameChangeHandler"
            />
        </ElFormItem>
        <!-- 邮箱 -->
        <EmailFormItem ref="emailFormRef" v-model="registerForm.email" data-cy="emailFormItem" check-collision="true" />
        <!-- 邮箱验证码 -->
        <EmailCodeBlock
            ref="emailCodeFormRef" v-model="registerForm.emailCode" :email="registerForm.email" type="register"
            :email-state="email_state"
        />
        <!-- 密码 -->
        <PasswordConfirmBlock ref="passwordFormRef" v-model="registerForm.password" data-cy="passwordFormItem" />
        <ElFormItem prop="agreeTAC">
            <!-- 同意协议 -->
            <div v-if="true" style="display: flex; align-items: center; flex-wrap: wrap; gap: 0.25em">
                <label class="checkbox">
                    <input v-model="agree_TAC" class="checkbox-input" type="checkbox" name="checkoutSecret" :aria-label="`${t('local.agreeTAC1')} ${t('local.agreeTAC2')}`">
                    <span>{{ t('local.agreeTAC1') }}</span>
                </label>
                <a target="_blank" rel="noopener noreferrer" :href="`${AXIOS_BASE_URL}/agreement.html`">{{ t('local.agreeTAC2') }}</a>
            </div>
            <!-- 确认 -->
            <BaseButton type="primary" :disabled="confirm_disabled" style="margin-left: auto" @click="submitForm(ruleFormRef!)">
                {{
                    t('common.button.register') }}
            </BaseButton>
        </ElFormItem>
    </ElForm>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import type { FormInstance } from 'element-plus';
import { ElForm, ElFormItem, ElInput, ElNotification } from 'element-plus';
import { computed, onUnmounted, reactive, ref, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import EmailCodeBlock from '@/components/formItems/EmailCodeBlock.vue';
import EmailFormItem from '@/components/formItems/EmailFormItem.vue';
import PasswordConfirmBlock from '@/components/formItems/PasswordConfirmBlock.vue';
import { local } from '@/store';
import { validateError, validateSuccess } from '@/utils/common/elFormValidate';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { ControlRegex, LineSeparatorRegex, MarkRegex, ParagraphSeparatorRegex, SpaceSeparatorRegex } from '@/utils/strings';

const emit = defineEmits(['login']);

const { proxy } = useCurrentInstance();
const agree_TAC = ref(false);
const AXIOS_BASE_URL = import.meta.env.VITE_BASE_API;

// Element Plus 2.8.0
// el-form 有 rule 属性实现更方便的校验，但是功能受限，
// 主要体现在多个校验器的优先级混乱，所以只能直接改 el-form-item 的内部变量
// el-form-item 有直接的 error 属性，可以实现完美的本地化
// 但是现版本控制不了 state，为了代码简洁，暂时不用 error 的解决方案
const usernameFormRef = useTemplateRef('usernameFormRef');
const emailFormRef = useTemplateRef<typeof EmailFormItem>('emailFormRef');
const emailCodeFormRef = useTemplateRef<typeof EmailCodeBlock>('emailCodeFormRef');
const passwordFormRef = useTemplateRef<typeof PasswordConfirmBlock>('passwordFormRef');

interface RegisterForm {
    username: string;
    password: string;
    email: string;
    emailCode: string;
}

const registerForm = reactive<RegisterForm>({
    username: '',
    password: '',
    email: '',
    emailCode: '',
});

const ruleFormRef = useTemplateRef('ruleFormRef');

const email_state = computed(() => {
    if (emailFormRef.value === null) return '';
    else return emailFormRef.value.validateState;
});
const confirm_disabled = computed(() => {
    return !(agree_TAC.value && usernameFormRef.value?.validateState === 'success' && emailFormRef.value?.validateState === 'success' && emailCodeFormRef.value?.validateState === 'success' && passwordFormRef.value?.validateState === 'success');
});

const usernameInputHandler = (value: string) => {
    if (usernameCharacterValidation(value)) return;
    else usernameFormRef.value?.clearValidate();
};

const usernameChangeHandler = (value: string) => {
    if (usernameCharacterValidation(value)) return;
    else {
        proxy.$axios.get('userprofile/checkcollision/', { params: { username: value } }).then(function (response) {
            if (response.data === 'False') validateSuccess(usernameFormRef);
            else validateError(usernameFormRef, t('msg.usernameCollision'));
        }).catch(function (error: unknown) {
            if (isAxiosError(error) && error.code === 'ERR_NETWORK') validateError(usernameFormRef, t('msg.connectionFail'));
            else validateError(usernameFormRef, `${t('msg.unknownError')}${error instanceof Error ? error.message : String(error)}`);
        });
    }
};

const submitForm = async (formEl?: FormInstance) => {
    if (!formEl) return;
    if (confirm_disabled.value) return;
    await proxy.$axios.post('userprofile/register/', {
        username: registerForm.username,
        password: registerForm.password,
        email: registerForm.email,
        email_key: emailCodeFormRef.value?.hashkey,
        email_captcha: registerForm.emailCode,
    }).then(function ({ data }) {
        if (data.type === 'success') {
            emit('login', data.user);
            ElNotification({
                title: t('msg.registerSuccess'),
                type: 'success',
                duration: local.value.notification_duration,
            });
        } else if (data.type === 'error') {
            if (data.object === 'emailcode') {
                emailCodeFormRef.value?.errorCode();
            }
        }
    });
};

onUnmounted(() => {
    if (ruleFormRef.value === null) return;
    ruleFormRef.value.resetFields();
});

const i18nMessages = {
    'zh-cn': { local: {
        agreeTAC1: '已阅读并同意',
        agreeTAC2: '开源扫雷网用户协议',
    } },
    en: { local: {
        agreeTAC1: 'Agree to',
        agreeTAC2: 'Terms & Conditions',
    } },
    de: { local: {
        confirm: 'bestätigen',
        agreeTAC1: 'Zustimmen',
        agreeTAC2: 'Nutzungsbedingungen',
    } },
};

const { t } = useI18n({ messages: i18nMessages });

function usernameCharacterValidation(value: string) {
    if (value.length == 0) validateError(usernameFormRef, t('msg.usernameRequired'));
    else if (ControlRegex.test(value)) validateError(usernameFormRef, t('msg.usernameCannotContainControl'));
    else if (LineSeparatorRegex.test(value)) validateError(usernameFormRef, t('msg.usernameCannotContainLineSeparator'));
    else if (ParagraphSeparatorRegex.test(value)) validateError(usernameFormRef, t('msg.usernameCannotContainParagraphSeparator'));
    else if (SpaceSeparatorRegex.test(value[0]) || SpaceSeparatorRegex.test(value[value.length - 1])) validateError(usernameFormRef, t('msg.usernameCannotStartOrEndWithSpace'));
    else if (MarkRegex.test(value[0])) validateError(usernameFormRef, t('msg.usernameCannotStartWithMark'));
    else return false;
    return true;
}
</script>
