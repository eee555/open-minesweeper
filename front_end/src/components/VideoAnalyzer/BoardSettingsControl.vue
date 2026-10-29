<template>
    <div class="board-settings-control button-group button-group--joined">
        <span class="board-settings-control__reference">
            <button ref="handle" class="base-button board-settings-control__handle" type="button" :aria-label="t('local.settings', { label })" :title="t('local.settings', { label })" aria-haspopup="dialog" :aria-expanded="settingsVisible" @keydown.esc.stop.prevent="closeSettings">
                <i :class="icon" aria-hidden="true" />
            </button>
        </span>
        <slot name="toggle" />
        <div hidden>
            <div ref="settings" class="board-settings-control__settings card card-small text text-small" role="dialog" :aria-label="t('local.settings', { label })" @keydown.esc.stop.prevent="closeSettings">
                <div class="board-settings-control__content">
                    <strong>{{ label }}</strong>
                    <slot name="settings" />
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import '@/styles/button.css';
import '@/styles/cards.css';
import 'primeicons/primeicons.css';
import { ref, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { useTippy } from 'vue-tippy';
import type { TippyOptions } from 'vue-tippy';

defineProps({ label: { type: String, required: true }, icon: { type: String, default: 'pi pi-ellipsis-v' } });
defineSlots<{
    toggle?: () => unknown;
    settings?: () => unknown;
}>();
const handle = useTemplateRef<HTMLButtonElement>('handle');
const settings = useTemplateRef<HTMLDivElement>('settings');
const settingsVisible = ref(false);
const appendToBody = () => document.body;
const popperOptions: TippyOptions['popperOptions'] = {
    modifiers: [
        { name: 'flip', enabled: false },
        { name: 'preventOverflow', options: { padding: 8, altAxis: true } },
    ],
};
// Tippy moves this Vue-owned element out of its hidden source container into the popover.
const { hide } = useTippy(handle, {
    content: () => settings.value ?? '',
    interactive: true,
    trigger: 'click',
    placement: 'left',
    role: 'presentation',
    appendTo: appendToBody,
    duration: 0,
    maxWidth: 'none',
    aria: { content: null, expanded: false },
    popperOptions,
    onShow,
    onHide,
    onMount: focusSettings,
});

function onShow() {
    settingsVisible.value = true;
}

function onHide() {
    settingsVisible.value = false;
}

function focusSettings() {
    settings.value?.querySelector<HTMLElement>('input, select, button')?.focus({ preventScroll: true });
}

function closeSettings() {
    hide();
    handle.value?.focus({ preventScroll: true });
}

defineExpose({ close: closeSettings });

const i18nMessages = {
    'zh-cn': { local: { settings: '{label}设置' } },
    en: { local: { settings: '{label} settings' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.board-settings-control {
    display: flex;
    align-items: center;
    flex: none;
}

.board-settings-control__handle {
    width: 12px;
    height: 28px;
    padding: 0;
    border-right: 0;
}

.board-settings-control__reference {
    display: flex;
    flex: none;
}

.board-settings-control__handle > i {
    font-size: 10px;
}

.board-settings-control__settings {
    width: 320px;
    max-width: calc(100vw - 16px);
    max-height: calc(100vh - 16px);
    overflow: auto;
}

.board-settings-control__content {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
}

.board-settings-control__content > :deep(*) {
    flex-shrink: 0;
}
</style>
