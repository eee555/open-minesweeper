<template>
    <BaseTable class="custom-counter-wrap" table-class="custom-counter" :table-style="tableStyle">
        <template #columns>
            <col :style="thColStyle">
            <col :style="tdColStyle">
        </template>
        <tr v-for="(row, index) in rows" :key="index">
            <th scope="row">
                {{ row.label }}
            </th>
            <td :class="{ 'custom-counter__value--error': row.error }">
                {{ row.value }}
            </td>
        </tr>
    </BaseTable>
</template>

<script setup lang="ts">
import { Parser } from 'expr-eval';
import type { PropType } from 'vue';
import { computed } from 'vue';

import { videoNumericParamKeys } from './types';
import type { CustomCounterConfig } from './types';

import BaseTable from '@/components/common/BaseTable.vue';
import type { AnyVideo } from '@/utils/fileIO';

const props = defineProps({
    video: { type: Object as PropType<AnyVideo>, required: true },
    currentMs: { type: Number, required: true },
    config: { type: Object as PropType<CustomCounterConfig>, required: true },
});

type DynamicParamValues = Record<string, unknown>;

const allowedKeys = new Set<string>(videoNumericParamKeys);
const parser = new Parser({
    operators: {
        assignment: false,
    },
});

const rows = computed(() => {
    // eslint-disable-next-line @typescript-eslint/no-meaningless-void-operator
    void props.currentMs;
    const values = createEvaluationContext(props.video);
    return props.config.table.map(([label, expression]) => {
        const result = evaluateExpression(expression, values);
        return {
            label,
            ...result,
        };
    });
});

const tableStyle = computed(() => ({
    fontSize: `${Math.max(1, props.config.fontSize)}px`,
    width: `${Math.max(1, props.config.thWidth) + Math.max(1, props.config.tdWidth)}px`,
}));

const thColStyle = computed(() => ({
    width: `${Math.max(1, props.config.thWidth)}px`,
}));

const tdColStyle = computed(() => ({
    width: `${Math.max(1, props.config.tdWidth)}px`,
}));

function evaluateExpression(expression: string, values: DynamicParamValues) {
    try {
        const parsed = parser.parse(expression);
        const unknownVariables = parsed.variables().filter((key) => !allowedKeys.has(key));
        if (unknownVariables.length > 0) throw new Error(`Unknown variable: ${unknownVariables.join(', ')}`);
        return { error: false, value: String(parsed.evaluate(values as Parameters<typeof parsed.evaluate>[0])) };
    } catch (error) {
        return { error: true, value: formatError(error) };
    }
}

function formatError(error: unknown) {
    if (error instanceof Error && error.message !== '') return error.message;
    return String(error);
}

function createEvaluationContext(video: AnyVideo) {
    const values: DynamicParamValues = {};
    for (const key of videoNumericParamKeys) {
        Object.defineProperty(values, key, {
            enumerable: true,
            get: () => video[key],
        });
    }
    return values;
}
</script>

<style scoped>
.custom-counter-wrap {
    max-height: calc(100vh - 290px);
    overflow-y: auto;
}

:deep(.custom-counter) {
    table-layout: fixed;
    border-collapse: collapse;
    color: var(--ui-text-color-regular);
    line-height: 1.25;
    background: transparent;
}

:deep(.custom-counter th),
:deep(.custom-counter td) {
    box-sizing: border-box;
    border: 1px solid var(--ui-border-color);
    padding: 3px 6px;
}

:deep(.custom-counter th) {
    color: var(--ui-text-color-secondary);
    font-weight: 500;
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    background: transparent;
}

:deep(.custom-counter td) {
    overflow: hidden;
    text-align: right;
    text-overflow: ellipsis;
    white-space: nowrap;
}

:deep(.custom-counter td.custom-counter__value--error) {
    color: var(--ui-color-danger);
    overflow-wrap: anywhere;
    text-align: left;
    white-space: normal;
}
</style>
