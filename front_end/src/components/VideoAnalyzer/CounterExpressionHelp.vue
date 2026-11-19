<template>
    <a class="counter-expression-help__link link text" :href="referenceUrl" target="_blank" rel="noopener noreferrer">
        {{ t('local.reference') }}
    </a>
</template>

<script setup lang="ts">
import '@/styles/link.css';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { getDocsUrl } from '@/utils/docs';

const referenceUrl = computed(() => getDocsUrl('guide/replay-expressions', locale.value));

const i18nMessages = {
    'zh-cn': { local: {
        reference: '表达式参考文档',
    } },
    en: { local: {
        reference: 'Expression reference',
    } },
    es: { local: {
        reference: 'Referencia de expresiones',
    } },
};
const { t, locale } = useI18n({ messages: i18nMessages });
</script>
