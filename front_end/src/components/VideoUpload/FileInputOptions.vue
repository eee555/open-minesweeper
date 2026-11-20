<template>
    <div class="file-input-options">
        <label class="checkbox" @click.stop>
            <input v-model="local.autoUploadAfterParse" class="checkbox-input" type="checkbox">
            <span>{{ t('local.autoUploadAfterParse') }}</span>
        </label>
        <label class="checkbox" @click.stop>
            <input v-model="local.autoRemoveAfterUpload" class="checkbox-input" type="checkbox">
            <span>{{ t('local.autoRemoveAfterUpload') }}</span>
        </label>
    </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

import { local } from '@/store';

/* 本地化 Localization */
const i18nMessages = {
    'zh-cn': { local: {
        autoUploadAfterParse: '解析完成自动上传',
        autoRemoveAfterUpload: '上传完成自动移除',
    } },
    en: { local: {
        autoUploadAfterParse: 'Auto-upload after parsing',
        autoRemoveAfterUpload: 'Auto-remove after uploading',
    } },
    es: { local: {
        autoUploadAfterParse: 'Subir automáticamente tras el análisis',
        autoRemoveAfterUpload: 'Quitar automáticamente tras la subida',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.file-input-options {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0 8px;
    cursor: default;
}
</style>
