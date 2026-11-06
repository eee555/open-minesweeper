<template>
    <div class="account-panel">
        <p class="text-secondary text-small">
            {{ t('local.privateNotice') }}
        </p>
        <UnverifiedNotice v-if="!verified" />
        <p v-else class="text-success">
            {{ t('accountlink.verified') }}
        </p>
    </div>
</template>

<script setup lang="ts">
import '../page.css';
import { useI18n } from 'vue-i18n';

import UnverifiedNotice from '@/components/accountlinks/UnverifiedNotice.vue';

defineProps({
    verified: { type: Boolean, default: false },
});

const i18nMessages = {
    'zh-cn': { local: {
        privateNotice: '私密关联，仅本人和本站管理员可见。',
    } },
    en: { local: {
        privateNotice: 'Private link, visible only to you and site moderators.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
