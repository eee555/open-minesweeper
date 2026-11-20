<template>
    <ElForm ref="ruleFormRef" :model="retrieveForm" status-icon>
        <!-- 邮箱 -->
        <EmailFormItem ref="emailFormRef" v-model="retrieveForm.email" check-collision="false" />
        <!-- 邮箱验证码 -->
        <EmailCodeBlock
            ref="emailCodeFormRef" v-model="retrieveForm.emailCode" :email="retrieveForm.email" type="register"
            :email-state="email_state"
        />
        <!-- 密码 -->
        <PasswordConfirmBlock ref="passwordFormRef" v-model="retrieveForm.password" />
        <!-- 确认 -->
        <ElFormItem>
            <BaseButton type="primary" :disabled="confirm_disabled" @click="submitForm(ruleFormRef!)">
                {{
                    t('local.confirm') }}
            </BaseButton>
        </ElFormItem>
    </ElForm>
</template>

<script setup lang="ts">
import type { FormInstance } from 'element-plus';
import { ElForm, ElFormItem, ElNotification } from 'element-plus';
import { computed, onUnmounted, reactive, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import EmailCodeBlock from '@/components/formItems/EmailCodeBlock.vue';
import EmailFormItem from '@/components/formItems/EmailFormItem.vue';
import PasswordConfirmBlock from '@/components/formItems/PasswordConfirmBlock.vue';
import { local } from '@/store';
import useCurrentInstance from '@/utils/common/useCurrentInstance';

const emit = defineEmits(['login']);

const { proxy } = useCurrentInstance();

const emailFormRef = useTemplateRef<typeof EmailFormItem>('emailFormRef');
const emailCodeFormRef = useTemplateRef<typeof EmailCodeBlock>('emailCodeFormRef');
const passwordFormRef = useTemplateRef<typeof PasswordConfirmBlock>('passwordFormRef');

interface RetrieveForm {
    email: string;
    emailCode: string;
    password: string;
}

const retrieveForm = reactive<RetrieveForm>({
    email: '',
    emailCode: '',
    password: '',
});

const ruleFormRef = useTemplateRef('ruleFormRef');

const email_state = computed(() => {
    if (emailFormRef.value === null) return '';
    else return emailFormRef.value.validateState;
});
const confirm_disabled = computed(() => {
    if (emailFormRef.value === null || emailCodeFormRef.value === null || passwordFormRef.value === null) return true;
    return emailFormRef.value.validateState !== 'success' || emailCodeFormRef.value.validateState !== 'success' || passwordFormRef.value.validateState !== 'success';
});

const submitForm = async (formEl?: FormInstance) => {
    if (!formEl) return;
    if (confirm_disabled.value) return;
    await proxy.$axios.post('userprofile/retrieve/', {
        password: retrieveForm.password,
        email: retrieveForm.email,
        email_key: emailCodeFormRef.value?.hashkey,
        email_captcha: retrieveForm.emailCode,
    }).then(function ({ data }) {
        if (data.type == 'success') {
            emit('login', data.user);
            ElNotification({
                title: t('msg.passwordChanged'),
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
        confirm: '更新密码',
    } },
    en: { local: {
        confirm: 'Update password',
    } },
    es: { local: {
        confirm: 'Actualizar contraseña',
    } },
    de: { local: {
        confirm: 'bestätigen',
    } },
    pl: { local: {
        confirm: 'Potwierdź',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
