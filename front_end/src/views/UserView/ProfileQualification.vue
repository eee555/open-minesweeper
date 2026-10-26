<template>
    <span v-if="store.qualificationStatus === 'idle' || store.qualificationStatus === 'loading'" class="text-info text-small" role="status">
        {{ t('local.loading') }}
    </span>
    <span v-else-if="store.qualificationStatus === 'error'" class="text-small text-warning" role="alert">
        {{ t('local.failed') }}
        <BaseButton size="small" text @click="store.loadQualification()">{{ t('button.retry') }}</BaseButton>
    </span>
</template>

<script setup lang="ts">
import { watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { profileDataRevision } from '@/services/profileDataService';
import { store } from '@/store';

watch([() => store.user, () => profileDataRevision(store.user.id)], () => {
    void store.loadQualification();
}, { immediate: true });
const i18nMessages = {
    'zh-cn': { local: {
        loading: '正在检查头像/签名修改资格…',
        failed: '资格查询失败。',
    } },
    en: { local: {
        loading: 'Checking avatar/signature eligibility…',
        failed: 'Could not check eligibility.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
