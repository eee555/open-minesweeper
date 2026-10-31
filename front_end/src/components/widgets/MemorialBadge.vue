<template>
    <span class="memorial-badge" data-cy="memorial-badge">{{ t('local.memorial') }}</span>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

const i18nMessages = {
    'zh-cn': { local: { memorial: '纪念账号' } },
    en: { local: { memorial: 'Memorial account' } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.memorial-badge {
    display: inline-block;
    margin-inline-start: 0.25rem;
    padding: 0 0.2rem;
    border: 1px solid var(--el-border-color);
    color: var(--el-text-color-secondary);
    font-size: 0.75rem;
    line-height: 1.4;
    white-space: nowrap;
}
</style>
