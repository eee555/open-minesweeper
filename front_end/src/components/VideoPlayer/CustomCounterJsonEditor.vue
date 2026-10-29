<template>
    <div class="custom-counter-json-editor">
        <ElInput
            v-model="configString"
            class="custom-counter-json-editor__input"
            type="textarea"
            @input="clearConfigError"
            @change="applyConfigString"
        />
        <div v-if="configErrorMessage !== ''" class="text-danger text-small">
            {{ configErrorMessage }}
        </div>
    </div>
</template>

<script setup lang="ts">

import { ElInput } from 'element-plus';
import type { PropType } from 'vue';
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { cloneCustomCounterTable, isCustomCounterTable } from './types';
import type { CustomCounterTableRow } from './types';

import { stringifyWithLineWrap } from '@/utils/strings';

const config = defineModel({
    type: Array as PropType<CustomCounterTableRow[]>,
    required: true,
});

const i18nMessages = {
    'zh-cn': { local: {
        invalidConfig: '配置必须是形如 [["label", "expression"]] 的二维字符串数组。',
        jsonParseFailed: 'JSON 解析失败：{message}',
    } },
    en: { local: {
        invalidConfig: 'Config must be a two-dimensional string array like [["label", "expression"]].',
        jsonParseFailed: 'Failed to parse JSON: {message}',
    } },
};

const { t } = useI18n({ messages: i18nMessages });

const configString = ref('');
const configErrorMessage = ref('');

watch(config, (value) => {
    configString.value = stringifyWithLineWrap(value);
    configErrorMessage.value = '';
}, { deep: true, immediate: true });

function applyConfigString(value: string) {
    try {
        const parsed = JSON.parse(value) as unknown;
        if (!isCustomCounterTable(parsed)) {
            configErrorMessage.value = t('local.invalidConfig');
            return;
        }
        config.value = cloneCustomCounterTable(parsed);
        configErrorMessage.value = '';
    } catch (error) {
        configErrorMessage.value = t('local.jsonParseFailed', { message: formatConfigError(error) });
    }
}

function clearConfigError() {
    configErrorMessage.value = '';
}

function formatConfigError(error: unknown) {
    if (error instanceof Error && error.message !== '') return error.message;
    return String(error);
}
</script>

<style scoped>
.custom-counter-json-editor {
    flex: 1 1 20em;
    display: flex;
    flex-direction: column;
    min-height: 0;
}

.custom-counter-json-editor__input {
    flex: 1 1 auto;
    width: 100%;
    min-height: 0;
    font-family: "Courier New", Courier, monospace;
}

:deep(.custom-counter-json-editor__input .el-textarea__inner) {
    height: 100%;
    min-height: 0 !important;
    overflow: auto;
    resize: none;
}
</style>
