<!-- 邮箱验证码表单项
    发送验证码的前置条件：填写了有效邮箱，且通过了图形验证 -->
<template>
    <!-- 图形验证码 -->
    <ElFormItem ref="captchaFormRef" :disabled="!email_success" :label="t('form.imageCaptcha')">
        <div style="display: flex">
            <ElInput
                v-model.trim="captcha" prefix-icon="Key" class="code" maxlength="4"
                @input="captchaHandler"
            />
            &nbsp;
            <ValidCode ref="refValidCode" />
        </div>
    </ElFormItem>
    <!-- 邮箱验证码 -->
    <ElFormItem ref="emailCodeFormRef" prop="emailCode" :label="t('form.emailCode')">
        <div style="display: flex">
            <ElInput
                v-model.trim="emailCode" data-cy="emailCode"
                prefix-icon="Key" maxlength="6" :disabled="captcha.length!=4" :placeholder="t(email_code_placeholder)"
                @input="emailCodeHandler"
            />
            &nbsp;
            <BaseButton :disabled="captcha.length != 4 || counting" @click="getEmailCaptcha(type)">
                <VueCountdown v-if="counting" v-slot="{ totalSeconds }" :time="60000" @end="counting = false;">
                    ({{ totalSeconds }})
                </VueCountdown>
                <span v-else>{{ t('button.send') }}</span>
            </BaseButton>
        </div>
    </ElFormItem>
</template>

<script setup lang="ts">
import VueCountdown from '@chenfengyuan/vue-countdown';
import { ElFormItem, ElInput, ElNotification } from 'element-plus';
import { computed, ref, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';

import ValidCode from '../ValidCode.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import { local } from '@/store';
import { validateError, validateSuccess } from '@/utils/common/elFormValidate';
import useCurrentInstance from '@/utils/common/useCurrentInstance';

const props = defineProps({
    type: { // 邮件模板，参考后端
        type: String,
        default: 'register',
    },
    email: {
        type: String,
        required: true,
    },
    emailState: { // 邮箱表单项的状态，参考el-form文档
        type: String,
        default: 'success',
    },
});
const emailCode = defineModel({ type: String, required: true });

const { proxy } = useCurrentInstance();
const { t } = useI18n();

const captcha = ref(''); // 图形验证码
const hashkey = ref(''); // 邮箱验证码hash
const email_success = ref(false); // 邮件发送成功
const email_handling = ref(false); // 正在校验图形验证码与发送邮件
const counting = ref(false);

const refValidCode = useTemplateRef('refValidCode');
const captchaFormRef = useTemplateRef('captchaFormRef');
const emailCodeFormRef = useTemplateRef('emailCodeFormRef');

// 获取验证状态
const validateState = computed(() => {
    return emailCodeFormRef.value?.validateState;
});

// 由外部验证后，若不正确则传入修改验证状态
const errorCode = () => {
    validateError(emailCodeFormRef, t('msg.emailCodeInvalid'));
};

defineExpose({ validateState, hashkey, errorCode });

const email_code_placeholder = computed(() => {
    if (props.emailState !== 'success') return t('msg.emailRequired');
    else if (captchaFormRef.value?.validateState !== 'success') return t('msg.captchaRequired');
    else if (email_handling.value) return t('msg.pleaseWait');
    else if (email_success.value) return t('msg.pleaseSeeEmail');
    else return '';
});

const captchaHandler = (value: string) => {
    if (value.length == 0) validateError(captchaFormRef, t('msg.captchaRequired'));
    else validateSuccess(captchaFormRef);
};

const emailCodeHandler = (value: string) => {
    if (value.length == 0) validateError(emailCodeFormRef, t('msg.emailCodeRequired'));
    else validateSuccess(emailCodeFormRef);
};

async function getEmailCaptcha(type: string) {
    if (props.emailState !== 'success') return;
    if (email_success.value) {
        refreshCaptcha();
        validateError(captchaFormRef, t('msg.captchaRefresh'));
        email_success.value = false;
        return;
    }
    email_handling.value = true;
    counting.value = true;
    await proxy.$axios.post('/userprofile/get_email_captcha/', {
        captcha: captcha.value,
        hashkey: refValidCode.value?.hashkey,
        email: props.email,
        type: type,
    }).then(function ({ data }) {
        if (data.type == 'success') {
            // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
            captchaFormRef.value!.validateState = 'success';
            hashkey.value = data.hashkey;
            email_success.value = true;
            ElNotification({
                title: t('msg.emailSendSuccessTitle'),
                message: t('msg.emailSendSuccessMsg'),
                type: 'warning',
                duration: local.value.notification_duration,
            });
        } else if (data.type == 'error') {
            refreshCaptcha();
            if (data.object == 'captcha') {
                validateError(captchaFormRef, t('msg.captchaFail'));
                counting.value = false;
            } else if (data.object == 'email') {
                validateError(captchaFormRef, t('msg.captchaRefresh'));
                ElNotification({
                    title: t('msg.emailSendFailTitle'),
                    message: t('msg.emailSendFailMsg'),
                    type: 'error',
                    duration: local.value.notification_duration,
                });
            }
        }
    });
    email_handling.value = false;
}

const refreshCaptcha = () => {
    refValidCode.value?.refreshPic();
    captcha.value = '';
};
</script>
