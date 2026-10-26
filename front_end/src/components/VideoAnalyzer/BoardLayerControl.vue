<template>
    <BoardSettingsControl class="board-layer-control" :label="label">
        <template #toggle>
            <slot name="toggle" />
        </template>
        <template #settings>
            <label class="checkbox checkbox--small">
                <input v-model="visible" class="board-layer-control__visible checkbox-input" type="checkbox">
                <span>{{ t('local.showLayer') }}</span>
            </label>
            <label class="board-layer-control__opacity-setting">
                <span>{{ t('common.prop.opacity') }}</span>
                <input v-model.number="opacity" class="board-layer-control__opacity" type="range" min="0" max="1" step="0.01">
                <output>{{ Math.round(opacity * 100) }}%</output>
            </label>
            <slot name="settings" />
        </template>
    </BoardSettingsControl>
</template>

<script setup lang="ts">
import '@/styles/checkbox.css';
import { useI18n } from 'vue-i18n';

import BoardSettingsControl from './BoardSettingsControl.vue';

defineProps({ label: { type: String, required: true } });
defineSlots<{
    toggle?: () => unknown;
    settings?: () => unknown;
}>();
const visible = defineModel({ type: Boolean, required: true });
const opacity = defineModel('opacity', { type: Number, required: true });

const i18nMessages = {
    'zh-cn': { local: {
        showLayer: '显示图层',
    } },
    en: { local: {
        showLayer: 'Show layer',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.board-layer-control__opacity-setting {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) 4ch;
    align-items: center;
    gap: 6px;
    font-variant-numeric: tabular-nums;
}

.board-layer-control__opacity {
    width: 100%;
    min-width: 0;
    margin: 0;
    accent-color: var(--ui-color-primary);
}

.board-layer-control__opacity-setting > output {
    text-align: right;
}
</style>
