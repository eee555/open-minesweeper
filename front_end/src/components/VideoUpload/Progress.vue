<template>
    <div v-if="isParsing" style="margin-top: 1em;">
        <span class="text-regular">
            {{ t('local.parsing', [parserProgress.parsed, parserProgress.total]) }}
        </span>
        &nbsp;
        <StackBar
            :data="[
                { name: t('local.parsed'), value: parserProgress.parsed, color: '#409EFF' },
                { name: t('local.toParse'), value: parserProgress.total - parserProgress.parsed, color: '#C0C4CC' },
            ]"
        />
    </div>
    <div v-if="isUploading" style="margin-top: 1em;">
        <span class="text-regular">
            {{ t('local.uploading', [uploadProgress.uploaded + uploadProgress.failed, uploadProgress.total]) }}
        </span>
        <StackBar
            :data="[
                { name: t('local.uploaded'), value: uploadProgress.uploaded, color: '#67C23A' },
                { name: t('local.uploadFailed'), value: uploadProgress.failed, color: '#F56C6C' },
                { name: t('local.toUpload'), value: uploadProgress.total - uploadProgress.uploaded - uploadProgress.failed, color: '#C0C4CC' },
            ]"
        />
    </div>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import type { ParserProgress, UploadProgress } from './utils';

import StackBar from '@/components/visualization/StackBar/App.vue';

const props = defineProps({
    parserProgress: {
        type: Object as PropType<ParserProgress>,
        default: () => ({ total: 0, parsed: 0 }),
    },
    uploadProgress: {
        type: Object as PropType<UploadProgress>,
        default: () => ({ total: 0, uploaded: 0, failed: 0 }),
    },
});

const isParsing = computed(() => props.parserProgress.total != props.parserProgress.parsed);
const isUploading = computed(() => props.uploadProgress.uploaded + props.uploadProgress.failed != props.uploadProgress.total);

/* 本地化 Localization */
const i18nMessages = {
    'zh-cn': { local: {
        parsing: '正在解析：{0} / {1}',
        parsed: '已解析',
        toParse: '待解析',
        uploading: '上传中：{0} / {1}',
        uploaded: '已上传',
        uploadFailed: '上传失败',
        toUpload: '待上传',
    } },
    en: { local: {
        parsing: 'Parsing files: {0} / {1}',
        parsed: 'Parsed',
        toParse: 'Not parsed',
        uploading: 'Uploading: {0} / {1}',
        uploaded: 'Uploaded',
        uploadFailed: 'Failed',
        toUpload: 'Queueing',
    } },
    es: { local: {
        parsing: 'Analizando archivos: {0}/{1}',
        parsed: 'Analizado',
        toParse: 'Sin analizar',
        uploading: 'Subiendo: {0}/{1}',
        uploaded: 'Subido',
        uploadFailed: 'Fallido',
        toUpload: 'En cola',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
