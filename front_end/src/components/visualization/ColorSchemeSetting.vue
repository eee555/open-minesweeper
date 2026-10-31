<template>
    <div class="color-scheme-setting text text-small">
        <div class="color-scheme-setting__actions">
            <BaseButton class="color-scheme-setting__reverse" size="small" :disabled="!canReverse" :title="t(canReverse ? 'local.reverse' : 'local.reverseUnavailable')" :aria-label="t('local.reverse')" @click="reverseIntervals">
                <span class="color-scheme-setting__interval-icon" aria-hidden="true">
                    <i class="pi" :class="[ascending ? 'pi-circle' : 'pi-circle-fill']" />
                    <span />
                    <i class="pi" :class="[ascending ? 'pi-circle-fill' : 'pi-circle']" />
                </span>
            </BaseButton>
            <BaseButton class="color-scheme-setting__import-toggle" size="small" :aria-expanded="importVisible" @click="toggleImport">
                <i class="pi pi-upload" aria-hidden="true" />{{ t('button.import') }}
            </BaseButton>
            <BaseButton class="color-scheme-setting__export" size="small" @click="exportScheme">
                <i class="pi pi-copy" aria-hidden="true" />{{ t('local.export') }}
            </BaseButton>
        </div>
        <div class="color-scheme-setting__rows">
            <div v-for="interval in intervals" :key="interval.index" class="color-scheme-setting__row">
                <div class="color-scheme-setting__interval">
                    <span v-if="interval.lowerIndex >= 0 && interval.lowerIndex < colorScheme.thresholds.length" class="color-scheme-setting__threshold-control">
                        <input v-model="thresholdDrafts[interval.lowerIndex]" class="color-scheme-setting__threshold" type="number" step="any" :min="min" :max="max" :aria-label="t('local.threshold', { index: interval.lowerIndex + 1 })" :aria-invalid="editError ? 'true' : undefined" @input="updateThreshold">
                        <BaseButton class="color-scheme-setting__remove" size="small" :title="t('local.merge')" :aria-label="t('local.merge')" @click="removeThreshold(interval.lowerIndex)">
                            <i class="pi pi-trash" aria-hidden="true" />
                        </BaseButton>
                    </span>
                    <input v-else class="color-scheme-setting__bound color-scheme-setting__threshold" type="text" :value="formatBound(interval.lower)" readonly tabindex="-1" :aria-label="t('local.lowerBound')">
                    <span class="color-scheme-setting__lower-comparison">{{ interval.lowerClosed ? '≤' : '<' }}</span>
                    <span>x</span>
                    <span class="color-scheme-setting__upper-comparison">{{ interval.upperClosed ? '≤' : '<' }}</span>
                    <span v-if="interval.upperIndex >= 0 && interval.upperIndex < colorScheme.thresholds.length" class="color-scheme-setting__threshold-control">
                        <input v-model="thresholdDrafts[interval.upperIndex]" class="color-scheme-setting__threshold" type="number" step="any" :min="min" :max="max" :aria-label="t('local.threshold', { index: interval.upperIndex + 1 })" :aria-invalid="editError ? 'true' : undefined" @input="updateThreshold">
                        <BaseButton class="color-scheme-setting__remove" size="small" :title="t('local.merge')" :aria-label="t('local.merge')" @click="removeThreshold(interval.upperIndex)">
                            <i class="pi pi-trash" aria-hidden="true" />
                        </BaseButton>
                    </span>
                    <input v-else class="color-scheme-setting__bound color-scheme-setting__threshold" type="text" :value="formatBound(interval.upper)" readonly tabindex="-1" :aria-label="t('local.upperBound')">
                </div>
                <BaseColorPicker class="color-scheme-setting__color" :model-value="interval.color" :aria-label="t('local.color', { index: interval.index + 1 })" @update:model-value="setColor(interval.index, $event)" />
                <BaseButton class="color-scheme-setting__split" size="small" :disabled="splitColorScheme(colorScheme, interval.index, min, max) === null" :title="t('local.split')" :aria-label="t('local.split')" @click="splitInterval(interval.index)">
                    <i class="pi pi-plus" aria-hidden="true" />
                </BaseButton>
            </div>
        </div>
        <p v-if="editError" class="color-scheme-setting__error contains" role="alert">
            {{ editError }}
        </p>
        <form v-if="importVisible" class="color-scheme-setting__import" @submit.prevent="importScheme">
            <textarea v-model="importJson" class="color-scheme-setting__json" :aria-label="t('local.json')" spellcheck="false" />
            <p v-if="importError" class="color-scheme-setting__error contains" role="alert">
                {{ importError }}
            </p>
            <div class="color-scheme-setting__actions">
                <BaseButton class="color-scheme-setting__apply" size="small" native-type="submit">
                    {{ t('button.import') }}
                </BaseButton>
                <BaseButton class="color-scheme-setting__cancel" size="small" @click="importVisible = false">
                    {{ t('button.cancel') }}
                </BaseButton>
            </div>
        </form>
    </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { colorSchemeError, colorSchemeIntervals, parseColorScheme, removeColorSchemeThreshold, splitColorScheme } from './colorScheme';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseColorPicker from '@/components/common/BaseColorPicker.vue';
import { copyToClipboard } from '@/components/widgets/CopyToClipboard';
import { ArrayUtils } from '@/utils/arrays';
import type { PiecewiseColorSchemeInterface } from '@/utils/colors';

const props = defineProps({
    min: { type: Number, default: -Infinity },
    max: { type: Number, default: Infinity },
});
const colorScheme = defineModel({ type: Object as PropType<PiecewiseColorSchemeInterface>, required: true });
const thresholdDrafts = ref<(string | number)[]>([]);
const editError = ref('');
const importVisible = ref(false);
const importJson = ref('');
const importError = ref('');
const ascending = computed(() => ArrayUtils.isAscending(colorScheme.value.thresholds));
const canReverse = computed(() => colorScheme.value.thresholds.length > 1 && colorScheme.value.thresholds[0] !== colorScheme.value.thresholds[colorScheme.value.thresholds.length - 1]);
const intervals = computed(() => colorSchemeIntervals(colorScheme.value, props.min, props.max).map((interval) => ({
    ...interval,
    lowerIndex: ascending.value ? interval.index - 1 : interval.index,
    upperIndex: ascending.value ? interval.index : interval.index - 1,
})).sort((a, b) => a.lower - b.lower || a.upper - b.upper));

watch(() => colorScheme.value.thresholds, (thresholds) => {
    thresholdDrafts.value = thresholds.map(String);
    editError.value = '';
}, { immediate: true, deep: true });

function formatBound(value: number): string {
    return value === Infinity ? '+∞' : value === -Infinity ? '-∞' : String(value);
}

function updateThreshold() {
    const thresholds = thresholdDrafts.value.map((value) => (typeof value === 'string' && value.trim() === '' ? NaN : Number(value)));
    const next = { colors: colorScheme.value.colors, thresholds };
    const error = colorSchemeError(next, props.min, props.max);
    editError.value = error === null ? '' : t('local.' + error);
    if (error === null) colorScheme.value = next;
}

function setColor(index: number, color: string) {
    const colors = [...colorScheme.value.colors];
    colors[index] = color;
    colorScheme.value = { thresholds: colorScheme.value.thresholds, colors };
}

function splitInterval(index: number) {
    const next = splitColorScheme(colorScheme.value, index, props.min, props.max);
    if (next !== null) colorScheme.value = next;
}

function removeThreshold(index: number) {
    colorScheme.value = removeColorSchemeThreshold(colorScheme.value, index);
}

function reverseIntervals() {
    if (!canReverse.value) return;
    colorScheme.value = { thresholds: [...colorScheme.value.thresholds].reverse(), colors: [...colorScheme.value.colors].reverse() };
}

function toggleImport() {
    importVisible.value = !importVisible.value;
    importError.value = '';
}

function importScheme() {
    try {
        colorScheme.value = parseColorScheme(importJson.value, props.min, props.max);
        importError.value = '';
        importVisible.value = false;
    } catch (error) {
        importError.value = error instanceof SyntaxError
            ? t('local.invalidJson') + ': ' + error.message
            : error instanceof Error ? t('local.' + error.message) : String(error);
    }
}

async function exportScheme() {
    try {
        await copyToClipboard(JSON.stringify(colorScheme.value, null, 2));
    } catch {
        // The shared clipboard helper already reports permission and availability failures.
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        reverse: '切换区间开闭',
        reverseUnavailable: '至少需要两个不同的分界点才能切换区间开闭',
        threshold: '分界点 {index}',
        lowerBound: '值域下限',
        upperBound: '值域上限',
        color: '区间 {index} 的颜色',
        split: '拆分区间',
        merge: '删除分界点',
        export: '导出',
        json: '粘贴色阶 JSON',
        invalidJson: 'JSON 格式错误',
        invalidShape: '需要 thresholds 和 colors 数组，颜色数量必须比分界点多一个。',
        invalidThresholds: '分界点必须是范围内的有限数值。',
        unsortedThresholds: '分界点必须按递增或递减顺序排列。',
        invalidColors: '颜色必须是有效的颜色字符串。',
    } },
    en: { local: {
        reverse: 'Switch interval boundaries',
        reverseUnavailable: 'At least two distinct thresholds are required to switch interval boundaries',
        threshold: 'Threshold {index}',
        lowerBound: 'Domain minimum',
        upperBound: 'Domain maximum',
        color: 'Color for interval {index}',
        split: 'Split interval',
        merge: 'Remove threshold',
        export: 'Export',
        json: 'Paste color scale JSON',
        invalidJson: 'Invalid JSON',
        invalidShape: 'Expected thresholds and colors arrays, with one more color than thresholds.',
        invalidThresholds: 'Thresholds must be finite numbers within the allowed range.',
        unsortedThresholds: 'Thresholds must be in ascending or descending order.',
        invalidColors: 'Colors must be valid color strings.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.color-scheme-setting {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
}
.color-scheme-setting__rows {
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow-x: auto;
}
.color-scheme-setting__row {
    display: grid;
    grid-template-columns: 11rem minmax(48px, 96px) 24px;
    align-items: center;
    gap: 4px;
    min-width: 256px;
}
.color-scheme-setting__interval {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 12px 8px 12px minmax(0, 1fr);
    align-items: center;
    gap: 2px;
    font-variant-numeric: tabular-nums;
    text-align: center;
}
.color-scheme-setting__bound {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: center;
}
.color-scheme-setting__threshold {
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
    height: 24px;
    padding: 0 2px;
    border: 0;
    background: transparent;
    color: var(--ui-text-color-regular);
    font: inherit;
    appearance: textfield;
}
.color-scheme-setting__threshold-control {
    display: flex;
    align-items: center;
    min-width: 0;
}
.color-scheme-setting__threshold-control > button {
    flex: none;
}
.color-scheme-setting__threshold::-webkit-inner-spin-button,
.color-scheme-setting__threshold::-webkit-outer-spin-button {
    appearance: none;
    margin: 0;
}
.color-scheme-setting__color {
    box-sizing: border-box;
    width: 100%;
    max-width: 96px;
    height: 18px;
    border: 1px solid var(--ui-border-color);
    background: var(--ui-fill-color-blank);
    color: var(--ui-text-color-regular);
    cursor: pointer;
}
.color-scheme-setting__color:focus-within {
    outline: 2px solid var(--ui-color-primary);
}
.color-scheme-setting__color :deep(.base-color-picker__clear) {
    width: 20px;
    background: var(--ui-fill-color-blank);
}
.color-scheme-setting__color :deep(.base-color-picker__clear:disabled) {
    color: var(--ui-disabled-text-color);
    cursor: default;
}
.color-scheme-setting__split,
.color-scheme-setting__remove,
.color-scheme-setting__reverse {
    width: 24px;
    height: 24px;
    padding: 0;
    margin: 0;
}
.color-scheme-setting__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
}
.color-scheme-setting__actions > button {
    margin: 0;
}
.color-scheme-setting__interval-icon {
    display: inline-flex;
    align-items: center;
    width: 18px;
}
.color-scheme-setting__interval-icon > i {
    font-size: 6px;
}
.color-scheme-setting__interval-icon > span {
    flex: 1;
    border-top: 1px solid currentColor;
}
.color-scheme-setting__import {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
}
.color-scheme-setting__json {
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
    height: 120px;
    resize: vertical;
    border: 1px solid var(--ui-border-color);
    padding: 4px;
    background: var(--ui-fill-color-blank);
    color: var(--ui-text-color-regular);
    font-family: monospace;
}
.color-scheme-setting__error {
    margin: 0;
    color: var(--ui-color-danger);
}
</style>
