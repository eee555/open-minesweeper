<template>
    <!-- 真实姓名 -->
    <div class="input-label" data-cy="real-name-section">
        <div class="text-large">
            {{ t('local.realname') }}
        </div>
        <div class="text-small">
            {{ t('local.realnameTooltip') }}
        </div>
        <div v-if="canChoosePrivacy" class="text-small">
            <label>
                <input v-model="hideRealname" type="checkbox" :disabled="updating" data-cy="hide-realname-toggle">
                {{ user.isAnonymous ? t('local.hideWithName') : t('local.hideRealname') }}
            </label>
            <p>{{ t('local.privacyScope') }}</p>
        </div>
        <p v-else-if="!user.isAnonymous" class="text-small">
            {{ t('local.privacyAuthorization') }}
        </p>
        <p v-if="privacyError" class="text-danger text-small">
            {{ privacyError }}
        </p>
    </div>

    <!-- 母语名 -->
    <div class="input-label">
        <div>{{ t('local.localname') }}</div>
        <div class="text-small">
            {{ t('local.localnameTooltip') }}
        </div>
    </div>
    <div>
        <div v-if="formStatus.realname.status === 'error'" class="text-danger text-small">
            {{ formStatus.realname.errorMsg }}
        </div>
        <div v-else-if="formStatus.realname.status === 'success'" class="text-small text-success">
            {{ t('local.updateSuccess') }}
        </div>
        <ElInput
            v-model="formStatus.realname.new" minlength="2"
            maxlength="100" show-word-limit :disabled="!user.isAnonymous" data-cy="name-realname"
        />
    </div>

    <!-- 英文姓名 -->
    <div class="input-label">
        <div>{{ t('local.englishName') }}</div>
        <div class="text-small">
            {{ t('local.englishNameTooltip') }}
        </div>
    </div>
    <div>
        <div v-if="formStatus.firstname.status === 'error'" class="text-danger text-small">
            {{ formStatus.firstname.errorMsg }}
        </div>
        <div v-else-if="formStatus.firstname.status === 'success'" class="text-small text-success">
            {{ t('local.updateSuccess') }}
        </div>
        <ElInput v-model="formStatus.firstname.new" :placeholder="t('local.firstname')" minlength="1" maxlength="255" show-word-limit :disabled="user.firstname !== ''" data-cy="name-firstname" />
        <div v-if="formStatus.lastname.status === 'error'" class="text-danger text-small">
            {{ formStatus.lastname.errorMsg }}
        </div>
        <div v-else-if="formStatus.lastname.status === 'success'" class="text-small text-success">
            {{ t('local.updateSuccess') }}
        </div>
        <ElInput v-model="formStatus.lastname.new" :placeholder="t('local.lastname')" minlength="1" maxlength="255" show-word-limit :disabled="user.lastname !== ''" data-cy="name-lastname" />
    </div>

    <!-- 个性签名 -->
    <div class="input-label">
        <div class="text-large">
            {{ t('local.signature') }}
        </div>
        <div class="text-small">
            {{ t('local.signatureTooltip', { left: user.newSignatureBudget(new Date(Date.now())), next: toISODateTimeString(user.nextSignatureAvailable) }) }}
        </div>
        <div v-if="qualificationStatus === 'ready' && expTimeMs >= 200000" class="text-small text-warning">
            {{ t('local.tooltipExpTime') }}
        </div>
    </div>
    <div>
        <div v-if="formStatus.signature.status === 'error'" class="text-danger text-small">
            {{ formStatus.signature.errorMsg }}
        </div>
        <div v-else-if="formStatus.signature.status === 'success'" class="text-small text-success">
            {{ t('local.updateSuccess') }}
        </div>
        <ElInput
            v-model="formStatus.signature.new" minlength="0"
            maxlength="4095" type="textarea" :rows="8" show-word-limit
            :disabled="signatureDisabled"
        />
    </div>

    <div style="margin-top: 1em">
        <BaseButton type="primary" :loading="updating" data-cy="save-profile" @click="updateProfile">
            {{ t('button.save') }}
        </BaseButton>
        <BaseButton type="info" :disabled="updating" @click="refresh">
            {{ t('button.cancel') }}
        </BaseButton>
    </div>
</template>

<script setup lang="ts">

import { ElInput } from 'element-plus';
import { computed, ref, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import { invalidateUserInfo } from '@/services/userService';
import type { EnumMap } from '@/utils';
import { createEnumMap } from '@/utils';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { globalNow, toISODateTimeString } from '@/utils/datetime';
import { hasRealname, HIDDEN_NAME, UserProfile } from '@/utils/userprofile';

const props = defineProps({
    expTimeMs: { type: Number, default: 999999 },
    qualificationStatus: { type: String as PropType<'idle' | 'loading' | 'ready' | 'error'>, default: 'ready' },
});

const { proxy } = useCurrentInstance();

const UpdateProfileFields = ['realname', 'firstname', 'lastname', 'signature'] as const;
type UpdateProfileField = typeof UpdateProfileFields[number];
interface formStatusSingle {
    new: string;
    status: '' | 'success' | 'error';
    errorMsg: string;
}

const user = defineModel<UserProfile>('user', { type: UserProfile, default: () => new UserProfile() });

const updating = ref(false);
const hideRealname = ref(false);
const privacyError = ref('');

const defaultFormStatus: formStatusSingle = {
    new: '',
    status: '',
    errorMsg: '',
};

const formStatus = ref<EnumMap<UpdateProfileField, formStatusSingle>>(
    createEnumMap(UpdateProfileFields, defaultFormStatus),
);

function refresh() {
    hideRealname.value = !user.value.isAnonymous && user.value.hide_realname;
    privacyError.value = '';
    for (const field of UpdateProfileFields) {
        formStatus.value[field].new = user.value[field];
        formStatus.value[field].status = '';
        formStatus.value[field].errorMsg = '';
    }
}

watch(user, refresh, { immediate: true });
const canChoosePrivacy = computed(() => user.value.can_hide_realname && hasRealname(formStatus.value.realname.new) && formStatus.value.realname.new.trim() !== HIDDEN_NAME);

const signatureDisabled = computed(() => props.qualificationStatus !== 'ready' || user.value.nextSignatureAvailable > globalNow.value || props.expTimeMs >= 200000);

type UpdateProfileResponseSingle = null
    | { type: 'success' }
    | { type: 'error'; object: string; category: string };

function processUpdateResponse(field: UpdateProfileField, data: UpdateProfileResponseSingle) {
    if (data === null) {
        formStatus.value[field].status = '';
        formStatus.value[field].errorMsg = '';
    } else if (data.type === 'success') {
        formStatus.value[field].status = 'success';
        formStatus.value[field].errorMsg = '';
        user.value[field] = formStatus.value[field].new;
        if (field === 'signature') {
            user.value.left_signature_n -= 1;
            user.value.last_change_signature = new Date(Date.now());
        }
    } else {
        formStatus.value[field].status = 'error';
        formStatus.value[field].errorMsg = t(data.object === 'name' && data.category === 'reserved' ? 'msg.reservedName' : `local.error.${data.object}.${data.category}`);
    }
}

async function updateProfile() {
    privacyError.value = '';
    let invalid = false;
    for (const field of ['realname', 'firstname', 'lastname'] as const) {
        if (formStatus.value[field].new.trim() === HIDDEN_NAME) {
            formStatus.value[field].status = 'error';
            formStatus.value[field].errorMsg = t('msg.reservedName');
            invalid = true;
        }
    }
    if (invalid) return;
    for (const field of UpdateProfileFields) {
        formStatus.value[field].status = '';
        formStatus.value[field].errorMsg = '';
    }
    updating.value = true;
    const owner = user.value;
    const params = new FormData();
    for (const field of UpdateProfileFields) {
        if (formStatus.value[field].new !== user.value[field]) {
            params.append(field, formStatus.value[field].new);
        }
    }
    if (canChoosePrivacy.value && hideRealname.value !== user.value.hide_realname) params.append('hide_realname', String(hideRealname.value));

    if (params.keys().next().done !== true) {
        await proxy.$axios.post(
            '/api/userprofile/update_profile',
            params,
        ).then(async (response) => {
            const data = response.data as EnumMap<UpdateProfileField, UpdateProfileResponseSingle> & { hide_realname?: UpdateProfileResponseSingle };
            if ([...UpdateProfileFields, 'hide_realname' as const].some((field) => data[field]?.type === 'success')) await invalidateUserInfo(owner.id);
            if (user.value !== owner) return;
            for (const field of UpdateProfileFields) {
                processUpdateResponse(field, data[field]);
            }
            if (data.hide_realname?.type === 'error') privacyError.value = t(data.hide_realname.object === 'name' && data.hide_realname.category === 'reserved' ? 'msg.reservedName' : `local.error.${data.hide_realname.object}.${data.hide_realname.category}`);
            if (data.hide_realname?.type === 'success') owner.hide_realname = hideRealname.value;
            hideRealname.value = !owner.isAnonymous && owner.hide_realname;
        }).catch((error: unknown) => {
            if (user.value === owner) hideRealname.value = !owner.isAnonymous && owner.hide_realname;
            httpErrorNotification(error);
        });
    }
    updating.value = false;
}

const i18nMessages = {
    'zh-cn': { local: {
        englishName: '英文姓名',
        englishNameTooltip: '用英文依次填写您的名和姓，让全世界的雷友认识您。',
        firstname: '名',
        lastname: '姓',
        localname: '本名',
        localnameTooltip: '使用您的本地语言填写完整姓名。这是上传录像所必需的信息。',
        realname: '真实姓名',
        realnameTooltip: '真实姓名一旦设置无法修改，请谨慎填写。如果有正当理由修改姓名，请联系管理员。',
        signature: '个性签名',
        tooltipExpTime: '高级sub200后才可以修改个性签名',
        updateSuccess: '修改成功',
        hideWithName: '同时隐藏实名',
        hideRealname: '隐藏实名',
        privacyAuthorization: '需要管理员授权或成功绑定 MSGames。已经绑定的用户可联系管理员补发资格。',
        privacyScope: '仅隐藏本站姓名，账号关联姓名和原始录像不受影响。由于缓存的原因，隐藏可能不会立刻生效。',
        signatureTooltip: ({ named }: { named: { (key: 'left'): number; (key: 'next'): string } }) => {
            if (named('left') > 0) {
                return `您每月可获得一次签名修改次数。当前剩余${named('left')}次。`;
            } else {
                return `您每月可获得一次签名修改次数。当前没有修改次数。下次可修改：${named('next')}`;
            }
        },
        error: {
            name: { exist: '姓名已经设置，请联系管理员修改' },
            database: { validation: '姓名格式不符合要求' },
            privacy: { realname_required: '请先填写有效实名', not_authorized: '尚未获得隐藏实名资格' },
            censorship: {
                unknown: '机器审核发生未知错误，请联系管理员',
                illegal: '未通过机器审核，请更换内容或联系管理员进行人工审核',
            },
        },
    } },
    en: { local: {
        englishName: 'International Name',
        englishNameTooltip: 'Fill in your given name and family name in English to let minesweepers around the world know you.',
        firstname: 'Given Name',
        lastname: 'Family Name',
        localname: 'Local Name',
        localnameTooltip: 'Fill in your full name in your local language. This field is required to upload videos.',
        realname: 'Real Name',
        realnameTooltip: 'Your real name cannot be changed once set. If you have a legitimate reason to change your name, please contact a moderator.',
        signature: 'Signature',
        tooltipExpTime: 'Achieve expert sub200 to change signature',
        updateSuccess: 'Update successful',
        hideWithName: 'Hide my real name when saving',
        hideRealname: 'Hide my real name',
        privacyAuthorization: 'Requires administrator approval or a successful MSGames binding. If already linked, ask an administrator to grant eligibility.',
        privacyScope: 'Hides site profile names. Linked account names and original replays are unaffected. Due to caching, name hiding may not take effect immediately.',
        signatureTooltip: ({ named }: { named: { (key: 'left'): number; (key: 'next'): string } }) => {
            if (named('left') > 0) {
                return `You gain one chance to modify your signature each month. You have ${named('left')} chances remaining.`;
            } else {
                return `You gain one chance to modify your signature each month. You have no chance remaining. Next available on: ${named('next')}`;
            }
        },
        error: {
            name: { exist: 'This name is already set. Contact an administrator to change it' },
            database: { validation: 'Invalid name format' },
            privacy: { realname_required: 'Enter a valid real name first', not_authorized: 'You are not authorized to hide your real name' },
            censorship: {
                unknown: 'Unknown error occurred in censorship. Please contact a moderator',
                illegal: 'The content is blocked by censorship. Please change the text or contact a moderator for manual review',
            },
        },
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style lang="less" scoped>
.input-label {
    margin-top: 0.75em;
    margin-bottom: 0.5em;
}
</style>
