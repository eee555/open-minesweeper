<template>
    <BaseTextButton underline="never" :aria-label="t('local.copy')" @click="copyToClipboard(text)">
        <BaseIconCopy />
    </BaseTextButton>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

import { copyToClipboard } from './CopyToClipboard';

import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { BaseIconCopy } from '@/components/common/icon';

defineProps({
    text: {
        type: String,
        default: '',
    },
});

const i18nMessages = {
    'zh-cn': { local: { copy: '复制' } },
    en: { local: { copy: 'Copy' } },
    es: { local: { copy: 'Copiar' } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
