<template>
    <div class="card card-small csv-import text-small">
        <div class="csv-controls">
            <BaseFileInput class="csv-file-input" accept=".csv,text/csv" :multiple="false" :disabled="!enabled || reading" data-cy="arbiter-csv-upload" @add="selectFiles">
                {{ t('local.selectFile') }}
            </BaseFileInput>
            <BaseButton v-if="hasCsv || failure || reading" size="small" data-cy="clear-arbiter-csv" @click="emit('clear')">
                {{ t('local.clear') }}
            </BaseButton>
        </div>
        <p v-if="reading" role="status" class="text-info">
            {{ t('local.reading') }}
        </p>
        <p v-else-if="failure" role="alert" class="text-danger">
            {{ issueText(failure) }}
        </p>
        <p v-else-if="hasCsv" role="status" data-cy="arbiter-csv-result">
            {{ filename }} · {{ t('local.count', { count }) }}
        </p>
        <details v-if="issues.length" class="csv-issues" data-cy="arbiter-csv-issues">
            <summary class="text-warning">
                {{ t('local.issues', { count: issues.length }) }}
            </summary>
            <ul>
                <li v-for="(issue, index) in issues.slice(0, 100)" :key="index">
                    {{ issueText(issue) }}
                </li>
            </ul>
            <p v-if="issues.length > 100">
                {{ t('local.more') }}
            </p>
        </details>
    </div>
</template>

<script setup lang="ts">
import '@/styles/cards.css';

import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { CsvIssue } from './arbiterCsv';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseFileInput from '@/components/common/BaseFileInput.vue';

defineProps({
    enabled: { type: Boolean, default: false },
    reading: { type: Boolean, default: false },
    hasCsv: { type: Boolean, default: false },
    filename: { type: String, default: '' },
    count: { type: Number, default: 0 },
    issues: { type: Array as PropType<CsvIssue[]>, default: () => [] },
    failure: { type: Object as PropType<CsvIssue>, default: undefined },
});
const emit = defineEmits<{ import: [file: File]; clear: [] }>();
function selectFiles(files: File[]) {
    const [file] = files;
    if (file !== undefined) emit('import', file);
}
function issueText(issue: CsvIssue) {
    const prefix = issue.row === undefined ? '' : t('local.row', { row: issue.row });
    return prefix + t(`local.${issue.code}`, { field: issue.field ?? '' });
}
const i18nMessages = {
    'zh-cn': { local: {
        selectFile: '选择 Arbiter CSV 文件',
        clear: '清除本地记录',
        reading: '正在读取 CSV…',
        count: '{count} 个本机未上传录像（仅本页临时展示）',
        issues: '{count} 条导入提示',
        more: '仅显示前 100 条提示。',
        row: '第 {row} 行：',
        headers: '缺少日期或 Time 表头，或存在重复表头。',
        quotes: 'CSV 引号结构不合法。',
        limit: 'CSV 不能超过 10 MiB 或 100,000 行。',
        date: '日期不合法，已跳过。',
        time: 'Time 不合法或精度超过毫秒，已跳过。',
        columns: '字段数量与表头不符；仅使用可读取的字段。',
        number: '{field} 不合法，按缺失值处理。',
        level: '未知等级 {field}，仍按日期与 Time 比较。',
        duplicate: '日期与 Time 重复，已合并。',
        mismatch: '同一录像的附加信息不同，不影响匹配结果。',
        missingEndTime: '部分已上传录像缺少结束时间，可能产生无法核实的本地记录。',
        read: '无法读取文件，请重新选择。',
    } },
    en: { local: {
        selectFile: 'Select an Arbiter CSV file',
        clear: 'Clear local records',
        reading: 'Reading CSV…',
        count: '{count} local videos not uploaded (temporary on this page)',
        issues: '{count} import notices',
        more: 'Only the first 100 notices are shown.',
        row: 'Line {row}: ',
        headers: 'Missing date or Time headers, or duplicate headers.',
        quotes: 'Invalid CSV quoting.',
        limit: 'CSV must not exceed 10 MiB or 100,000 rows.',
        date: 'Invalid date; skipped.',
        time: 'Invalid Time or precision beyond milliseconds; skipped.',
        columns: 'Column count differs from the header; only readable fields are used.',
        number: 'Invalid {field}; treated as missing.',
        level: 'Unknown level {field}; still compared by date and Time.',
        duplicate: 'Duplicate date and Time; merged.',
        mismatch: 'Other details differ for the same video; the match is retained.',
        missingEndTime: 'Some uploaded videos have no end time; local records may be unverifiable.',
        read: 'Could not read the file. Please select it again.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.csv-import {
    margin: 0.4rem 0;
}
.csv-controls {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 5px;
}
.csv-file-input {
    width: auto;
    max-width: 100%;
}
.csv-import p {
    margin: 5px 0 0;
}
.csv-issues {
    margin-top: 5px;
}
.csv-issues summary {
    cursor: pointer;
}
.csv-issues ul {
    max-height: 12rem;
    overflow: auto;
    margin: 5px 0 0;
    padding-inline-start: 1.5em;
}
</style>
