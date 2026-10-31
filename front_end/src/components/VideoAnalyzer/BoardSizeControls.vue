<template>
    <div class="board-size-controls button-group button-group--joined" role="group" :aria-label="t('prop.cellSize')">
        <BoardSettingsControl class="board-size-controls__fixed" :label="t('local.fixed')">
            <template #toggle>
                <BaseButton class="board-size-controls__fixed-toggle board-size-controls__toggle" size="small" :type="mode === 'fixed' ? 'primary' : 'default'" :aria-label="t('local.fixed')" :title="t('local.fixed')" :aria-pressed="mode === 'fixed'" @click="mode = 'fixed'">
                    {{ fixedSize }}px
                </BaseButton>
            </template>
            <template #settings>
                <div class="board-size-controls__presets button-group button-group--joined">
                    <BaseButton v-for="size in fixedPresets" :key="size" class="board-size-controls__fixed-preset" size="small" :type="fixedSize === size ? 'primary' : 'default'" @click="fixedSize = size">
                        {{ size }}px
                    </BaseButton>
                </div>
                <label class="board-size-controls__input-setting">
                    <span>{{ t('local.pixels') }}</span>
                    <InputNumber v-model="fixedSize" class="board-size-controls__fixed-input" :min="1" step="1" />
                </label>
            </template>
        </BoardSettingsControl>
        <BoardSettingsControl class="board-size-controls__relative" :label="t('local.relative')">
            <template #toggle>
                <BaseButton class="board-size-controls__relative-toggle board-size-controls__toggle" size="small" :type="mode === 'relative' ? 'primary' : 'default'" :aria-label="t('local.relative')" :title="t('local.relative')" :aria-pressed="mode === 'relative'" @click="mode = 'relative'">
                    {{ scalePercent }}%
                </BaseButton>
            </template>
            <template #settings>
                <div class="board-size-controls__presets button-group button-group--joined">
                    <BaseButton v-for="percent in scalePresets" :key="percent" class="board-size-controls__relative-preset" size="small" :type="scalePercent === percent ? 'primary' : 'default'" @click="scalePercent = percent">
                        {{ percent }}%
                    </BaseButton>
                </div>
                <label class="board-size-controls__input-setting">
                    <span>{{ t('local.percent') }}</span>
                    <InputNumber v-model="scalePercent" class="board-size-controls__relative-input" :min="1" step="1" />
                </label>
            </template>
        </BoardSettingsControl>
        <BaseButton class="board-size-controls__auto-toggle board-size-controls__toggle" size="small" :type="mode === 'auto' ? 'primary' : 'default'" :aria-label="t('local.auto')" :title="t('local.auto')" :aria-pressed="mode === 'auto'" @click="mode = 'auto'">
            <i class="pi pi-expand" aria-hidden="true" />
        </BaseButton>
    </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import BoardSettingsControl from './BoardSettingsControl.vue';
import type { CellSizeMode } from './config';

import BaseButton from '@/components/common/BaseButton.vue';
import InputNumber from '@/components/common/InputNumber.vue';

const mode = defineModel<CellSizeMode>({ required: true });
const fixedSize = defineModel<number>('fixedSize', { required: true });
const scale = defineModel<number>('scale', { required: true });
const fixedPresets = [16, 24, 32, 48];
const scalePresets = [50, 100, 150, 200];
const scalePercent = computed({
    get: () => Number((scale.value * 100).toPrecision(12)),
    set: (percent: number) => {
        scale.value = percent / 100;
    },
});

const i18nMessages = {
    'zh-cn': { local: {
        fixed: '固定数值',
        relative: '相对比例',
        auto: '自适应',
        pixels: '格子边长 (px)',
        percent: '比例 (%)',
    } },
    en: { local: {
        fixed: 'Fixed size',
        relative: 'Relative scale',
        auto: 'Adaptive size',
        pixels: 'Cell size (px)',
        percent: 'Scale (%)',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.board-size-controls {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
}

.board-size-controls__toggle {
    width: 56px;
    height: 28px;
    padding: 0 2px;
    margin: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-variant-numeric: tabular-nums;
}

.board-size-controls__presets {
    display: flex;
    flex-wrap: wrap;
}

.board-size-controls__input-setting {
    display: flex;
    align-items: center;
    gap: 8px;
}

.board-size-controls__input-setting input {
    width: 100px;
}
</style>
