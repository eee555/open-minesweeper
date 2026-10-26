<template>
    <div class="mouse-trace-settings">
        <details class="mouse-trace-settings__lines" open>
            <summary>{{ t('local.lines') }}</summary>
            <label class="mouse-trace-settings__field">
                <span>{{ t('local.lineWidth') }}</span>
                <InputNumber v-model="appearance.lineWidth" class="mouse-trace-settings__line-width" :min="0" step="any" />
            </label>
            <label v-for="state in mouseTraceStates" :key="state" class="mouse-trace-settings__field">
                <span>{{ t(`local.${state}`) }}</span>
                <BaseColorPicker v-model="appearance.color[state]" class="mouse-trace-settings__color" :class="`mouse-trace-settings__color--${state}`" :aria-label="t(`local.${state}`)" />
            </label>
        </details>
        <details v-for="action in mouseTraceMarkerActions" :key="action" class="mouse-trace-settings__marker" :class="`mouse-trace-settings__marker--${action}`">
            <summary>{{ t(`local.${action}`) }}</summary>
            <label class="checkbox checkbox--small">
                <input v-model="appearance.markers[action].enabled" class="checkbox-input mouse-trace-settings__enabled" type="checkbox">
                <span>{{ t('local.showMarker') }}</span>
            </label>
            <fieldset class="mouse-trace-settings__fields" :disabled="!appearance.markers[action].enabled">
                <label class="mouse-trace-settings__field">
                    <span>{{ t('common.prop.shape') }}</span>
                    <select v-model="appearance.markers[action].shape" class="mouse-trace-settings__shape">
                        <option v-for="shape in mouseTraceMarkerShapes" :key="shape" :value="shape">{{ t(`local.${shape}`) }}</option>
                    </select>
                </label>
                <label class="mouse-trace-settings__field">
                    <span>{{ t('local.size') }}</span>
                    <InputNumber v-model="appearance.markers[action].size" class="mouse-trace-settings__size" :min="0" step="any" />
                </label>
                <label class="mouse-trace-settings__field">
                    <span>{{ t('local.fill') }}</span>
                    <BaseColorPicker v-model="appearance.markers[action].fill" class="mouse-trace-settings__color mouse-trace-settings__fill" :disabled="!appearance.markers[action].enabled" :aria-label="t('local.fill')" />
                </label>
                <label class="mouse-trace-settings__field">
                    <span>{{ t('local.stroke') }}</span>
                    <BaseColorPicker v-model="appearance.markers[action].stroke" class="mouse-trace-settings__color mouse-trace-settings__stroke" :disabled="!appearance.markers[action].enabled" :aria-label="t('local.stroke')" />
                </label>
                <label class="mouse-trace-settings__field">
                    <span>{{ t('local.strokeWidth') }}</span>
                    <InputNumber v-model="appearance.markers[action].strokeWidth" class="mouse-trace-settings__stroke-width" :min="0" step="any" />
                </label>
                <label class="mouse-trace-settings__field">
                    <span>{{ t('common.prop.opacity') }}</span>
                    <InputNumber v-model="appearance.markers[action].opacity" class="mouse-trace-settings__opacity" :min="0" :max="1" step="0.01" />
                </label>
            </fieldset>
        </details>
    </div>
</template>

<script setup lang="ts">
import '@/styles/checkbox.css';
import { mouseTraceMarkerActions, mouseTraceMarkerShapes, mouseTraceStates } from '@putianyi888/vue3-minesweeper-board';
import { useI18n } from 'vue-i18n';

import type { MouseTraceAppearance } from './mouseTrace';

import BaseColorPicker from '@/components/common/BaseColorPicker.vue';
import InputNumber from '@/components/common/InputNumber.vue';

const appearance = defineModel<MouseTraceAppearance>({ required: true });

const i18nMessages = {
    'zh-cn': { local: {
        lines: '线条',
        lineWidth: '线宽 (格)',
        uu: '未按键',
        du: '左键按下',
        ud: '右键按下',
        dd: '双键按下',
        lc: '左键按下标记',
        lr: '左键释放标记',
        rc: '右键按下标记',
        rr: '右键释放标记',
        showMarker: '显示标记',
        size: '大小 (格)',
        fill: '填充色',
        stroke: '描边色',
        strokeWidth: '描边宽度 (格)',
        circle: '圆点',
        ring: '圆环',
        cross: '十字',
        square: '方形',
        diamond: '菱形',
    } },
    en: { local: {
        lines: 'Lines',
        lineWidth: 'Line width (cells)',
        uu: 'No buttons held',
        du: 'Left button held',
        ud: 'Right button held',
        dd: 'Both buttons held',
        lc: 'Left press marker',
        lr: 'Left release marker',
        rc: 'Right press marker',
        rr: 'Right release marker',
        showMarker: 'Show marker',
        size: 'Size (cells)',
        fill: 'Fill color',
        stroke: 'Stroke color',
        strokeWidth: 'Stroke width (cells)',
        circle: 'Circle',
        ring: 'Ring',
        cross: 'Cross',
        square: 'Square',
        diamond: 'Diamond',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.mouse-trace-settings {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
}

.mouse-trace-settings summary {
    cursor: pointer;
}

.mouse-trace-settings__fields {
    margin: 0;
    padding: 0;
    border: 0;
    min-width: 0;
}

.mouse-trace-settings__field {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 100px;
    align-items: center;
    gap: 6px;
    margin-top: 4px;
}

.mouse-trace-settings__field > input,
.mouse-trace-settings__field > select {
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
}

.mouse-trace-settings__shape {
    height: 24px;
    border: 1px solid var(--ui-border-color);
    border-radius: 0;
    background: var(--ui-fill-color-blank);
    color: var(--ui-text-color-regular);
    font: inherit;
}

.mouse-trace-settings__color {
    width: 100%;
    height: 18px;
    cursor: pointer;
}

.mouse-trace-settings__fields:disabled {
    opacity: 0.5;
}
</style>
