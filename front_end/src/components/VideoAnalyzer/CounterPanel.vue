<template>
    <section class="text text-small video-analyzer-counter" :aria-label="t('local.counter')">
        <div ref="rowsViewport" class="video-analyzer-counter__rows">
            <div class="video-analyzer-counter__columns">
                <BaseTable v-for="(column, index) in columns" :key="index" class="video-analyzer-counter__column" :table-style="{ width: `${config.thWidth + config.tdWidth}px`, tableLayout: 'fixed' }">
                    <template #columns>
                        <col :style="{ width: `${config.thWidth}px` }"><col :style="{ width: `${config.tdWidth}px` }">
                    </template>
                    <tr v-for="row in column" :key="row.key">
                        <th scope="row">
                            <div class="video-analyzer-counter__label">
                                <Tippy interactive trigger="click" placement="right" :append-to="appendToBody" :duration="0">
                                    <BaseButton class="video-analyzer-counter__handle" :title="t('local.rowMenu')" :aria-label="t('local.rowMenu')">
                                        <i class="pi pi-ellipsis-v" aria-hidden="true" />
                                    </BaseButton>
                                    <template #content="{ hide }">
                                        <div class="video-analyzer-counter__menu">
                                            <div class="button-group button-group--joined video-analyzer-counter__menu-actions">
                                                <BaseButton class="video-analyzer-counter__add-above" @click="hide(); openAdd(row.key, false)">
                                                    <i class="pi pi-plus" aria-hidden="true" />{{ t('local.addAbove') }}
                                                </BaseButton>
                                                <BaseButton class="video-analyzer-counter__add-below" @click="hide(); openAdd(row.key, true)">
                                                    <i class="pi pi-plus" aria-hidden="true" />{{ t('local.addBelow') }}
                                                </BaseButton>
                                                <BaseButton class="video-analyzer-counter__move" @click="hide(); openMove(row.key)">
                                                    <i class="pi pi-arrows-v" aria-hidden="true" />{{ t('local.move') }}
                                                </BaseButton>
                                                <BaseButton class="video-analyzer-counter__edit" @click="hide(); editKey = row.key">
                                                    <i class="pi pi-pencil" aria-hidden="true" />{{ t('button.edit') }}
                                                </BaseButton>
                                            </div>
                                            <label>
                                                {{ t('local.sendToSlot') }}
                                                <select class="video-analyzer-counter__send-to-slot" :aria-label="t('local.sendToSlot')" :disabled="slotNames.length === 0" value="" @change="sendToSlot($event, row.key); hide()">
                                                    <option value="" disabled>{{ t('local.sendToSlot') }}</option>
                                                    <option v-for="(name, index) in slotNames" :key="index" :value="index">{{ name }}</option>
                                                </select>
                                            </label>
                                        </div>
                                    </template>
                                </Tippy>
                                <span :title="row.key">{{ row.key }}</span>
                            </div>
                        </th>
                        <td><span class="video-analyzer-counter__value" :class="{ 'text-danger': row.error }" :title="row.value">{{ row.value }}</span></td>
                    </tr>
                </BaseTable>
            </div>
        </div>
        <footer class="button-group button-group--joined video-analyzer-counter__actions">
            <BaseButton class="video-analyzer-counter__settings" :title="t('local.settings')" :aria-label="t('local.settings')" @click="dialog = 'settings'">
                <i class="pi pi-cog" aria-hidden="true" />
            </BaseButton>
            <BaseButton class="video-analyzer-counter__import" :title="t('local.import')" :aria-label="t('local.import')" @click="openImport">
                <i class="pi pi-upload" aria-hidden="true" />
            </BaseButton>
            <BaseButton class="video-analyzer-counter__export" :title="t('local.export')" :aria-label="t('local.export')" @click="exportConfig">
                <i class="pi pi-copy" aria-hidden="true" />
            </BaseButton>
        </footer>
        <CounterRowEditor v-if="editRow" :key="editRow.key" :row="editRow" :creating="addTarget !== null" :existing-keys="config.rows.map(row => row.key)" :events="events" :current-ms="currentMs" :duration-ms="durationMs" @save="saveRow" @close="editKey = null; addTarget = null" />
        <ElDialog v-if="dialog" v-model="dialogVisible" :title="t(`local.${dialog}`)" width="min(480px, calc(100vw - 24px))" append-to-body @closed="dialog = null">
            <form id="counter-config-form" class="video-analyzer-counter__form" @submit.prevent="applyDialog">
                <template v-if="dialog === 'settings'">
                    <label><span>{{ t('local.labelWidth') }}</span><InputNumber v-model="thWidth" class="base-input video-analyzer-counter__label-width" step="any" /></label>
                    <label><span>{{ t('local.valueWidth') }}</span><InputNumber v-model="tdWidth" class="base-input video-analyzer-counter__value-width" step="any" /></label>
                </template>
                <label v-else-if="dialog === 'move'"><span>{{ t('local.offset') }}</span><InputNumber v-model="offset" class="base-input video-analyzer-counter__offset" :step="1" /></label>
                <textarea v-else v-model="importJson" class="video-analyzer-counter__json" :aria-label="t('local.json')" spellcheck="false" @input="dialogError = ''" />
                <p v-if="dialogError" class="contains text-danger" role="alert">
                    {{ dialogError }}
                </p>
            </form>
            <template #footer>
                <div class="button-group button-group--joined video-analyzer-counter__dialog-actions">
                    <BaseButton class="video-analyzer-counter__cancel" @click="dialogVisible = false">
                        {{ t('button.cancel') }}
                    </BaseButton>
                    <BaseButton class="video-analyzer-counter__apply" type="primary" native-type="submit" form="counter-config-form">
                        {{ t('local.apply') }}
                    </BaseButton>
                </div>
            </template>
        </ElDialog>
    </section>
</template>

<script setup lang="ts">
import '@/styles/text.css';
import { useElementSize, useRafFn } from '@vueuse/core';
import { ElDialog } from 'element-plus';
import { computed, ref, useTemplateRef, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import { counterError, displayCounter, moveCounterRow, parseCounterConfig, prepareCounters } from './counter';
import type { CounterConfig, CounterEvent, CounterRow, PreparedCounter } from './counter';
import CounterRowEditor from './CounterRowEditor.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import InputNumber from '@/components/common/InputNumber.vue';
import { copyToClipboard } from '@/components/widgets/CopyToClipboard';

const props = defineProps({
    events: { type: Array as PropType<CounterEvent[]>, required: true },
    currentMs: { type: Number, required: true },
    durationMs: { type: Number, default: undefined },
    counters: { type: Object as PropType<Map<string, PreparedCounter>>, default: null },
    slotNames: { type: Array as PropType<string[]>, default: () => [] },
});
const emit = defineEmits<{ sendToSlot: [target: { key: string; slotIndex: number }] }>();
const config = defineModel<CounterConfig>({ required: true });
const rowsViewport = useTemplateRef('rowsViewport');
const { height } = useElementSize(rowsViewport);
const rowsPerColumn = ref(1);
// Reflow columns outside ResizeObserver delivery to avoid a synchronous resize loop.
const { resume: updateColumns } = useRafFn(() => {
    rowsPerColumn.value = Math.max(1, Math.floor((height.value - 20) / 28));
}, { immediate: false, once: true });
watch(height, updateColumns, { immediate: true });
const prepared = computed(() => props.counters ?? prepareCounters(config.value.rows, props.events, props.durationMs));
const columns = computed(() => {
    const rows = config.value.rows.map((row) => {
        const counter = prepared.value.get(row.key);
        return { ...row, ...props.events.length && counter ? displayCounter(counter, props.currentMs) : { value: '--', error: false } };
    });
    const result: typeof rows[] = [];
    for (let index = 0; index < rows.length; index += rowsPerColumn.value) result.push(rows.slice(index, index + rowsPerColumn.value));
    return result;
});
const appendToBody = () => document.body;
const editKey = ref<string | null>(null);
const addTarget = ref<{ key: string; after: boolean } | null>(null);
const editRow = computed<CounterRow | undefined>(() => (addTarget.value ? { key: '', expression: '', format: '.3f', samplingMode: 'button' } : config.value.rows.find((row) => row.key === editKey.value)));
const dialog = ref<'settings' | 'import' | 'move' | null>(null);
const dialogVisible = ref(false);
const dialogError = ref('');
const importJson = ref('');
const thWidth = ref(80);
const tdWidth = ref(96);
const offset = ref(0);
let movingKey = '';

function sendToSlot(event: Event, key: string) {
    const select = event.target as HTMLSelectElement;
    emit('sendToSlot', { key, slotIndex: Number(select.value) });
    select.value = '';
}

watch(dialog, (value) => {
    if (value === null) return;
    dialogVisible.value = true;
    dialogError.value = '';
    thWidth.value = config.value.thWidth;
    tdWidth.value = config.value.tdWidth;
});

function saveRow(row: CounterRow) {
    if (addTarget.value) {
        const index = config.value.rows.findIndex((entry) => entry.key === addTarget.value?.key);
        if (index < 0) return;
        const rows = [...config.value.rows];
        rows.splice(index + Number(addTarget.value.after), 0, row);
        config.value = { ...config.value, rows };
    } else config.value = { ...config.value, rows: config.value.rows.map((entry) => (entry.key === row.key ? row : entry)) };
}

function openAdd(key: string, after: boolean) {
    editKey.value = null;
    addTarget.value = { key, after };
}

function openMove(key: string) {
    movingKey = key;
    offset.value = 0;
    dialog.value = 'move';
}

function openImport() {
    importJson.value = '';
    dialog.value = 'import';
}

function applyDialog() {
    try {
        if (dialog.value === 'import') config.value = parseCounterConfig(importJson.value);
        else if (dialog.value === 'settings') config.value = { ...config.value, thWidth: thWidth.value, tdWidth: tdWidth.value };
        else {
            if (!Number.isInteger(offset.value)) throw new Error('integerOffset');
            config.value = { ...config.value, rows: moveCounterRow(config.value.rows, movingKey, offset.value) };
        }
        dialogVisible.value = false;
    } catch (error) {
        const message = counterError(error);
        dialogError.value = error instanceof SyntaxError ? `${t('local.invalidJson')}: ${message}` : ['invalidConfig', 'duplicateKey', 'integerOffset'].includes(message) ? t(`local.${message}`) : message;
    }
}

async function exportConfig() {
    try {
        await copyToClipboard(JSON.stringify(config.value, null, 2));
    } catch {
        // The shared clipboard helper already reports failures.
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        counter: '计数器',
        rowMenu: '行操作',
        addAbove: '在上方添加',
        addBelow: '在下方添加',
        move: '移动位置',
        sendToSlot: '发送到 plot',
        settings: '通用设置',
        import: '导入配置',
        export: '导出到剪贴板',
        labelWidth: 'key 列宽 (px)',
        valueWidth: '数值列宽 (px)',
        offset: '偏移量',
        json: 'JSON 配置',
        apply: '应用',
        invalidJson: 'JSON 解析失败',
        invalidConfig: '配置结构无效',
        duplicateKey: '行 key 不能重复',
        integerOffset: '偏移量必须是整数',
    } },
    en: { local: {
        counter: 'Counters',
        rowMenu: 'Row actions',
        addAbove: 'Add above',
        addBelow: 'Add below',
        move: 'Move',
        sendToSlot: 'Send to plot',
        settings: 'General settings',
        import: 'Import config',
        export: 'Copy config',
        labelWidth: 'Key width (px)',
        valueWidth: 'Value width (px)',
        offset: 'Offset',
        json: 'JSON config',
        apply: 'Apply',
        invalidJson: 'Invalid JSON',
        invalidConfig: 'Invalid config structure',
        duplicateKey: 'Row keys must be unique',
        integerOffset: 'Offset must be an integer',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-analyzer-counter {
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    height: 100%;
    min-width: 0;
    min-height: 0;
    color: var(--el-text-color-primary);
    background: var(--ui-bg-color);
}

.video-analyzer-counter__rows {
    flex: 1;
    min-height: 0;
    overflow-x: auto;
    overflow-y: hidden;
}

.video-analyzer-counter__columns {
    display: flex;
    align-items: flex-start;
    width: max-content;
}

.video-analyzer-counter__column {
    flex: none;
    max-width: none;
    overflow: visible;
}

.video-analyzer-counter__column :deep(tr) {
    height: 28px;
}

.video-analyzer-counter__column :deep(th),
.video-analyzer-counter__column :deep(td) {
    height: 28px;
    padding: 0 4px;
    overflow: hidden;
    font-weight: normal;
}

.video-analyzer-counter__label {
    display: flex;
    align-items: center;
    gap: 2px;
    height: 26px;
}

.video-analyzer-counter__label > span,
.video-analyzer-counter__value {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.video-analyzer-counter__label > :first-child {
    flex: none;
}

.video-analyzer-counter__value {
    text-align: right;
    font-variant-numeric: tabular-nums;
}

.video-analyzer-counter__handle {
    width: 8px;
    height: 24px;
    padding: 0;
    border: 0;
    background: transparent;
}

.video-analyzer-counter__handle i {
    font-size: 8px;
}

.video-analyzer-counter__actions {
    display: flex;
    flex: none;
    padding: 4px;
}

.video-analyzer-counter__actions button {
    width: 28px;
    height: 24px;
    padding: 0;
    margin: 0;
}

.video-analyzer-counter__menu,
.video-analyzer-counter__form {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.video-analyzer-counter__menu button {
    justify-content: flex-start;
    margin: 0;
}
.video-analyzer-counter__menu-actions {
    flex-direction: column;
}
.video-analyzer-counter__dialog-actions {
    justify-content: flex-end;
}

.video-analyzer-counter__form label {
    display: grid;
    grid-template-columns: 9em minmax(0, 1fr);
    align-items: center;
    gap: 8px;
}

.video-analyzer-counter__json {
    box-sizing: border-box;
    width: 100%;
    height: 240px;
    max-height: 50vh;
    padding: 4px;
    resize: vertical;
    color: var(--el-text-color-primary);
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color);
    font-family: monospace;
}
</style>
