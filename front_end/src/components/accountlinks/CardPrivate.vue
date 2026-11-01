<template>
    <BaseCardNormal>
        <h3 class="text-medium text-regular">
            {{ t(`platform.${platform}`) }} #{{ id }}
        </h3>
        <p class="text-secondary text-small">
            {{ t('local.privateNotice') }}
        </p>
        <UnverifiedNotice v-if="!verified" />
        <p v-else class="text-success">
            {{ t('accountlink.verified') }}
        </p>
    </BaseCardNormal>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import UnverifiedNotice from './UnverifiedNotice.vue';

import BaseCardNormal from '@/components/common/BaseCardNormal.vue';

defineProps({
    platform: { type: String as PropType<'d' | 'q'>, required: true },
    id: { type: String, required: true },
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
