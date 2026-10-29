<template>
    <label class="checkbox checkbox--small identifier-display-options">
        <input v-model="showInvisibleIdentifiers" class="checkbox-input" type="checkbox">
        <span>{{ t('local.showInvisible') }}</span>
    </label>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

import { showInvisibleIdentifiers } from './identifierDisplay';

const i18nMessages = {
    'zh-cn': { local: { showInvisible: '显示不可见字符' } },
    en: { local: { showInvisible: 'Show invisible characters' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.identifier-display-options {
    align-self: flex-start;
    width: fit-content;
}
</style>
