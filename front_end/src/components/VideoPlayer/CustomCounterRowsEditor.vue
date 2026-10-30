<template>
    <div class="custom-counter-rows-editor">
        <VueDraggable
            v-model="draggableRows"
            class="custom-counter-rows-editor__draggable-rows"
            handle=".custom-counter-rows-editor__drag-handle"
            ghost-class="custom-counter-rows-editor__drag-ghost"
            :animation="150"
        >
            <div
                v-for="(row, index) in draggableRows"
                :key="index"
                class="custom-counter-rows-editor__row"
            >
                <i class="custom-counter-rows-editor__drag-handle pi pi-ellipsis-v text-secondary" />
                <ElInput
                    class="custom-counter-rows-editor__label"
                    :model-value="row[0]"
                    size="small"
                    @input="(value: string) => updateLabel(index, value)"
                    @change="() => commitRowLabel(index)"
                />
                <ElInput
                    class="custom-counter-rows-editor__expression"
                    :model-value="row[1]"
                    size="small"
                    type="textarea"
                    :autosize="expressionAutosize"
                    @input="(value: string) => updateExpression(index, value)"
                />
            </div>
        </VueDraggable>
        <div class="custom-counter-rows-editor__row">
            <span class="custom-counter-rows-editor__drag-spacer" />
            <ElInput
                v-model="newRowLabel"
                class="custom-counter-rows-editor__label"
                size="small"
                @change="addNewRow"
            />
            <ElInput
                v-model="newRowExpression"
                class="custom-counter-rows-editor__expression"
                size="small"
                type="textarea"
                :autosize="expressionAutosize"
                @change="addNewRow"
            />
        </div>
    </div>
</template>

<script setup lang="ts">
import 'primeicons/primeicons.css';

import { ElInput } from 'element-plus';
import type { PropType } from 'vue';
import { computed, ref, watch } from 'vue';
import { VueDraggable } from 'vue-draggable-plus';

import { cloneCustomCounterTable } from './types';
import type { CustomCounterTableRow } from './types';

const config = defineModel({
    type: Array as PropType<CustomCounterTableRow[]>,
    required: true,
});

const newRowLabel = ref('');
const newRowExpression = ref('');
const editableRows = ref<CustomCounterTableRow[]>([]);
const expressionAutosize = { minRows: 1, maxRows: 4 };
let skipNextEditableRowsSync = false;

const draggableRows = computed<CustomCounterTableRow[]>({
    get: () => editableRows.value,
    set: (nextRows) => {
        editableRows.value = nextRows;
        updateConfigFromRows(nextRows);
    },
});

watch(config, (value) => {
    if (skipNextEditableRowsSync) {
        skipNextEditableRowsSync = false;
        return;
    }
    editableRows.value = cloneCustomCounterTable(value);
}, { deep: true, immediate: true });

function addNewRow() {
    const label = newRowLabel.value.trim();
    if (label === '') return;

    const nextRows = [
        ...editableRows.value,
        [label, newRowExpression.value === '' ? '0' : newRowExpression.value] satisfies CustomCounterTableRow,
    ];
    editableRows.value = nextRows;
    updateConfigFromRows(nextRows);
    newRowLabel.value = '';
    newRowExpression.value = '';
}

function updateLabel(index: number, label: string) {
    editableRows.value = editableRows.value.map((row, rowIndex): CustomCounterTableRow => {
        return rowIndex === index ? [label, row[1]] : row;
    });
}

function commitRowLabel(index: number) {
    const row = editableRows.value[index];

    const trimmedLabel = row[0].trim();
    if (trimmedLabel === '') {
        removeRow(index);
        return;
    }

    row[0] = trimmedLabel;
    updateConfigFromRows(editableRows.value);
}

function updateExpression(index: number, expression: string) {
    const nextRows = editableRows.value.map((row, rowIndex): CustomCounterTableRow => {
        return rowIndex === index ? [row[0], expression] : row;
    });
    editableRows.value = nextRows;
    updateConfigFromRows(nextRows);
}

function removeRow(index: number) {
    const nextRows = editableRows.value.filter((_, rowIndex) => rowIndex !== index);
    editableRows.value = nextRows;
    updateConfigFromRows(nextRows);
}

function updateConfigFromRows(rows: CustomCounterTableRow[]) {
    skipNextEditableRowsSync = true;
    config.value = cloneCustomCounterTable(rows);
}
</script>

<style scoped>
.custom-counter-rows-editor {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-height: 20em;
    overflow: auto;
}

.custom-counter-rows-editor__draggable-rows {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.custom-counter-rows-editor__row {
    display: grid;
    grid-template-columns: 8px minmax(92px, 0.35fr) minmax(220px, 1fr);
    gap: 6px;
    align-items: center;
}

.custom-counter-rows-editor__drag-handle,
.custom-counter-rows-editor__drag-spacer {
    width: 8px;
}

.custom-counter-rows-editor__drag-handle {
    cursor: grab;
    font-size: 14px;
}

.custom-counter-rows-editor__drag-handle:active {
    cursor: grabbing;
}

.custom-counter-rows-editor__drag-ghost {
    opacity: 0.55;
}

.custom-counter-rows-editor__label,
.custom-counter-rows-editor__expression {
    font-family: "Courier New", Courier, monospace;
}

:deep(.custom-counter-rows-editor__expression .el-textarea__inner) {
    resize: none;
    overflow-wrap: anywhere;
}
</style>
