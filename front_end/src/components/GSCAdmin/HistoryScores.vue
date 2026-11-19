<template>
    <p>{{ t('local.csvHeader') }}<code>{{ historyCsvHeaders(kind).join(',') }}</code>{{ t('local.milliseconds') }}</p>
    <input type="file" accept=".csv" :disabled="busy" :aria-label="t('local.scoresFile')" data-cy="history-csv" @change="selectCsv">
    <BaseButton :disabled="!records.length || submitted" :loading="busy" data-cy="history-csv-submit" @click="submit">
        {{ t('local.import') }} {{ records.length }} {{ t('local.records') }}
    </BaseButton>
    <p v-if="error" role="alert" data-cy="history-csv-error">
        {{ error }}
    </p>
    <p data-cy="history-csv-progress">
        {{ t('local.confirmed') }} {{ confirmed }} / {{ records.length }}
    </p>
    <ul data-cy="history-csv-batches">
        <li v-for="message in messages" :key="message">
            {{ message }}
        </li>
    </ul>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { historyCsvHeaders, parseHistoryCsv, splitHistoryBatches } from './history';
import type { HistoryCsvRecord, HistoryKind } from './history';

import BaseButton from '@/components/common/BaseButton.vue';
import { importGSCHistoryScores } from '@/services/gscHistoryService';

const props = defineProps({ kind: { type: String as PropType<HistoryKind>, required: true } });
const emit = defineEmits<{ imported: [] }>();
const i18nMessages = {
    'zh-cn': { local: {
        batchSuccess: '第 {order} 届，CSV 行 {lines}：成功 {count} 条',
        batchFailed: '第 {order} 届，CSV 行 {lines}：{reason}。后续批次未提交。超时可能已写入，请先核对管理列表，再用仅含剩余记录的 CSV 重试。',
        unsent: '未提交 CSV 行：{lines}',
        milliseconds: '。成绩单位：毫秒。',
        csvHeader: 'CSV 表头：',
        scoresFile: '成绩 CSV',
        confirmed: '已确认成功',
        records: '条成绩',
        import: '导入',
    } },
    en: { local: {
        batchSuccess: 'Edition {order}, CSV rows {lines}: {count} imported',
        batchFailed: 'Edition {order}, CSV rows {lines}: {reason}. Later batches were not submitted. A timeout can occur after a write. Check the list before retrying with a CSV containing only the remaining rows.',
        unsent: 'CSV rows not submitted: {lines}',
        milliseconds: '. Scores are in milliseconds.',
        csvHeader: 'CSV header: ',
        scoresFile: 'Results CSV',
        confirmed: 'Confirmed',
        records: 'scores',
        import: 'Import',
    } },
    es: { local: {
        batchSuccess: 'Edición {order}, filas {lines} del CSV: {count} importadas',
        batchFailed: 'Edición {order}, filas {lines} del CSV: {reason}. Los lotes posteriores no se enviaron. Si caducó la solicitud, es posible que se haya guardado. Comprueba la lista antes de reintentar con un CSV que contenga solo las filas pendientes.',
        unsent: 'Filas del CSV sin enviar: {lines}',
        milliseconds: '. Las puntuaciones se expresan en milisegundos.',
        csvHeader: 'Cabecera del CSV: ',
        scoresFile: 'CSV de resultados',
        confirmed: 'Confirmados',
        records: 'resultados',
        import: 'Importar',
    } },
};
const { t } = useI18n({ messages: i18nMessages });

const records = ref<HistoryCsvRecord[]>([]);
const confirmed = ref(0);
const submitted = ref(false);
const busy = ref(false);
const error = ref('');
const messages = ref<string[]>([]);
let stopped = false;
onBeforeUnmount(() => {
    stopped = true;
});

async function selectCsv(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    records.value = [];
    confirmed.value = 0;
    submitted.value = false;
    messages.value = [];
    error.value = '';
    if (!file) return;
    busy.value = true;
    try {
        records.value = parseHistoryCsv(await file.text(), props.kind);
    } catch (reason) {
        error.value = String(reason);
    } finally {
        busy.value = false;
    }
}

async function submit() {
    if (busy.value || submitted.value || !records.value.length) return;
    busy.value = true;
    submitted.value = true;
    const batches = splitHistoryBatches(records.value);
    try {
        for (const [index, batch] of batches.entries()) {
            if (stopped) break;
            const lines = batch.records.map((record) => record.sourceRow).join(', ');
            try {
                const count = await importGSCHistoryScores(props.kind, batch.order, batch.records.map((record) => record.data));
                confirmed.value += count;
                messages.value.push(t('local.batchSuccess', { order: batch.order, lines, count }));
            } catch (reason) {
                error.value = t('local.batchFailed', { order: batch.order, lines, reason: String(reason) });
                const remaining = batches.slice(index + 1).flatMap((pending) => pending.records.map((record) => record.sourceRow));
                if (remaining.length) messages.value.push(t('local.unsent', { lines: remaining.join(', ') }));
                break;
            }
        }
    } finally {
        busy.value = false;
        emit('imported');
    }
}
</script>
