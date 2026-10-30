<template>
    <div class="board-event-settings">
        <label class="board-event-settings__field">
            <span>{{ t('local.timeRange') }}</span>
            <select v-model="settings.timeRange" class="board-event-settings__range">
                <option value="all">{{ t('local.all') }}</option>
                <option value="past">{{ t('local.past') }}</option>
            </select>
        </label>
        <fieldset class="board-event-settings__selection">
            <legend>{{ t('local.events') }}</legend>
            <label v-for="event in definitions" :key="event.key" class="checkbox checkbox--small">
                <input v-model="settings.keys" class="board-event-settings__key checkbox-input" type="checkbox" :value="event.key">
                <span>{{ event.key }}</span>
            </label>
        </fieldset>
        <label class="board-event-settings__field">
            <span>{{ t('local.spacing') }}</span>
            <input v-model.number="settings.arrowSpacing" class="board-event-settings__spacing" type="number" min="1" step="1">
        </label>
        <label class="board-event-settings__field">
            <span>{{ t('local.size') }}</span>
            <input v-model.number="settings.arrowSize" class="board-event-settings__size" type="number" min="1" step="1">
        </label>
        <label class="board-event-settings__field">
            <span>{{ t('local.shape') }}</span>
            <select v-model="settings.arrowShape" class="board-event-settings__shape">
                <option value="triangle">{{ t('local.triangle') }}</option>
                <option value="open">{{ t('local.open') }}</option>
            </select>
        </label>
    </div>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { BoardEventSettings } from './boardEvents';
import type { CustomEventDefinition } from './customEvents';

defineProps({ definitions: { type: Array as PropType<CustomEventDefinition[]>, required: true } });
const settings = defineModel<BoardEventSettings>({ required: true });
const i18nMessages = {
    'zh-cn': { local: {
        timeRange: '时间范围',
        all: '全局',
        past: '当前时间点及之前',
        events: '自定义事件',
        spacing: '箭头间距 (px)',
        size: '箭头大小 (px)',
        shape: '箭头形状',
        triangle: '实心三角',
        open: '开放箭头',
    } },
    en: { local: {
        timeRange: 'Time range',
        all: 'Entire replay',
        past: 'Up to current time',
        events: 'Custom events',
        spacing: 'Arrow spacing (px)',
        size: 'Arrow size (px)',
        shape: 'Arrow shape',
        triangle: 'Filled triangle',
        open: 'Open arrow',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.board-event-settings,
.board-event-settings__selection {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
}
.board-event-settings__selection {
    margin: 0;
    padding: 6px;
    max-height: 160px;
    overflow: auto;
    border: 1px solid var(--ui-border-color);
}
.board-event-settings__selection span {
    overflow-wrap: anywhere;
}
.board-event-settings__field {
    display: grid;
    grid-template-columns: 1fr minmax(0, 1fr);
    align-items: center;
    gap: 6px;
}
.board-event-settings__field :is(input, select) {
    min-width: 0;
    width: 100%;
    box-sizing: border-box;
    font: inherit;
    color: var(--ui-text-color-regular);
    background: var(--ui-bg-color);
    border: 1px solid var(--ui-border-color);
}
</style>
