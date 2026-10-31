<template>
    <ElInput v-model="identifier" />
    <BaseButton @click="handleGet">
        {{ t('button.query') }}
    </BaseButton>
    <BaseButton v-if="safe == 'false'" @click="handleApprove">
        {{ t('button.approve') }}
    </BaseButton>
    <template v-if="identifier !== ''">
        <br>&nbsp;
        {{ t('local.linkUserId') }}
        <ElInputNumber v-model="newUserid" :min="0" :precision="0" />
        <BaseButton @click="handleAdd">
            {{ t('button.link') }}
        </BaseButton>
    </template>
    <br>
    {{ t('local.summary', { userId: userid, status: t(`local.${safe}`) }) }}
</template>

<script setup lang="ts">
import { ElInput, ElInputNumber } from 'element-plus';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { httpErrorNotification, successNotification } from '@/components/Notifications';
import useCurrentInstance from '@/utils/common/useCurrentInstance';

const { proxy } = useCurrentInstance();

const identifier = ref('');
const safe = ref('unknown');
const userid = ref(0);
const newUserid = ref(0);

function handleGet() {
    proxy.$axios.get('identifier/get/staff/', { params: { identifier: identifier.value } }).then(
        function (response) {
            safe.value = (response.data.safe as boolean).toString();
            userid.value = response.data.user ?? 0;
        },
    ).catch(httpErrorNotification);
}

function handleApprove() {
    proxy.$axios.post('/api/identifier/safe', { identifier: identifier.value, safe: true }).then(
        function (response) {
            safe.value = 'true';
            successNotification(response);
        },
    ).catch(httpErrorNotification);
}

function handleAdd() {
    proxy.$axios.post<{ safe: boolean; user_id: number | null }>('/api/identifier/bind', { identifier: identifier.value, id: newUserid.value }).then(
        function (response) {
            safe.value = response.data.safe.toString();
            userid.value = response.data.user_id ?? 0;
            successNotification(response);
        },
    ).catch(httpErrorNotification);
}

const i18nMessages = {
    'zh-cn': { local: {
        linkUserId: '绑定用户 ID（0 表示解绑）',
        summary: '用户 ID：{userId}，状态：{status}',
        unknown: '未知',
        true: '已通过审核',
        false: '待审核',
    } },
    en: { local: {
        linkUserId: 'Link to user ID (0 to unbind)',
        summary: 'User ID: {userId}, status: {status}',
        unknown: 'Unknown',
        true: 'Approved',
        false: 'Pending approval',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
