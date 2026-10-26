<template>
    <div class="minigame-settings" :class="{ 'description-layout': descriptionLayout, 'minigame-settings--descriptions': descriptionLayout }">
        <dl :class="descriptionLayout ? 'descriptions' : 'minigame-settings-list'">
            <div :class="descriptionLayout ? 'description-item' : 'minigame-settings-row'">
                <dt><label :for="cellSizeId">{{ t('local.cellSize') }}</label></dt>
                <dd class="minigame-settings-controls">
                    <InputNumber :id="cellSizeId" v-model="minigameSettings.cellSize" :min="1" :max="Number.MAX_SAFE_INTEGER" integer step="1" inputmode="numeric" data-cy="minigame-cell-size" />
                    <span>px</span>
                </dd>
            </div>
            <div :class="descriptionLayout ? 'description-item' : 'minigame-settings-row'">
                <dt><label :for="hotkeyId">{{ t('local.restartHotkey') }}</label></dt>
                <dd class="minigame-settings-controls">
                    <input :id="hotkeyId" type="text" readonly :value="formatRestartHotkey(minigameSettings.restartHotkey)" :placeholder="t('local.unset')" :aria-describedby="hintId" data-cy="minigame-restart-hotkey" @keydown="recordHotkey">
                    <BaseButton size="small" :disabled="minigameSettings.restartHotkey === null" data-cy="minigame-clear-hotkey" @click="minigameSettings.restartHotkey = null">
                        {{ t('local.clear') }}
                    </BaseButton>
                </dd>
            </div>
            <div :class="descriptionLayout ? 'description-item' : 'minigame-settings-row'">
                <dt><label :for="opacityId">{{ t('local.mineOpacity') }}</label></dt>
                <dd class="minigame-settings-controls minigame-settings-opacity">
                    <input :id="opacityId" v-model.number="minigameSettings.leftClickMineOpacity" type="range" min="0" max="1" step="0.01" :aria-valuetext="`${Math.round(minigameSettings.leftClickMineOpacity * 100)}%`" data-cy="minigame-mine-opacity">
                    <output :for="opacityId" data-cy="minigame-mine-opacity-value">{{ Math.round(minigameSettings.leftClickMineOpacity * 100) }}%</output>
                </dd>
            </div>
            <div :class="descriptionLayout ? 'description-item' : 'minigame-settings-row'">
                <dt :id="mineStateId">
                    {{ t('local.mineState') }}
                </dt>
                <dd class="minigame-settings-controls">
                    <div class="checkbox-buttons" role="radiogroup" :aria-labelledby="mineStateId" data-cy="minigame-mine-state">
                        <label v-for="state in ['up', 'down']" :key="state" class="checkbox-button">
                            <input v-model="minigameSettings.leftClickMinePressed" class="checkbox-button-input" type="radio" :name="mineStateId" :value="state === 'down'" :data-cy="`minigame-mine-${state}`">
                            <span class="checkbox-button-content">{{ t(`local.${state}`) }}</span>
                        </label>
                    </div>
                </dd>
            </div>
        </dl>
        <p :id="hintId" class="minigame-settings-hint text text-info text-small">
            {{ t('local.hint') }}
        </p>
    </div>
</template>

<script setup lang="ts">
import '@/styles/checkbox-buttons.css';
import '@/styles/descriptions.css';

import { useId } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import InputNumber from '@/components/common/InputNumber.vue';
import { formatRestartHotkey, restartHotkeyFromEvent } from '@/utils/minigame/hotkey';
import { minigameSettings } from '@/utils/minigame/settings';

defineProps({ descriptionLayout: { type: Boolean, default: false } });
const hintId = useId();
const hotkeyId = useId();
const cellSizeId = useId();
const opacityId = useId();
const mineStateId = useId();

function recordHotkey(event: KeyboardEvent) {
    if (event.key === 'Tab') return;
    event.preventDefault();
    event.stopPropagation();
    const hotkey = restartHotkeyFromEvent(event);
    if (hotkey !== null) minigameSettings.value.restartHotkey = hotkey;
}

const i18nMessages = {
    'zh-cn': { local: {
        cellSize: '格子大小',
        restartHotkey: '重开热键',
        unset: '未设置',
        clear: '清除',
        hint: '点击输入框后按键设置，支持组合键；所有小游戏共用。输入参数时不触发重开。',
        mineOpacity: '左键／多指训练 · 雷的不透明度',
        mineState: '左键／多指训练 · 雷格状态',
        up: '弹起',
        down: '按下',
    } },
    en: { local: {
        cellSize: 'Cell size',
        restartHotkey: 'Restart hotkey',
        unset: 'Not set',
        clear: 'Clear',
        hint: 'Focus the field and press a key or combination. Shared by all games; inactive while editing settings.',
        mineOpacity: 'Left-click / multi-touch training · Mine opacity',
        mineState: 'Left-click / multi-touch training · Mine cell state',
        up: 'Raised',
        down: 'Pressed',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.minigame-settings {
    display: grid;
    gap: 0.25rem;
}

.minigame-settings-list {
    display: grid;
    gap: 0.25rem;
    margin: 0;
    padding: 0;
}

.minigame-settings-row,
.minigame-settings-controls,
.minigame-settings-list {
    min-width: 0;
}

.minigame-settings-row,
.minigame-settings-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
}

.minigame-settings-list :is(dt, dd) {
    margin: 0;
}

.minigame-settings:not(.minigame-settings--descriptions) {
    text-align: center;
}

.minigame-settings-list .minigame-settings-row,
.minigame-settings-list .minigame-settings-controls {
    justify-content: center;
}

.minigame-settings--descriptions .minigame-settings-hint {
    padding-inline: 8px;
}

.minigame-settings.minigame-settings--descriptions input[type='text'] {
    text-align: start;
}

.minigame-settings input[type='text'] {
    max-width: 100%;
    box-sizing: border-box;
    padding: 0.25rem;
    border: 1px solid var(--ui-border-color);
    border-radius: 0;
    color: var(--ui-text-color-regular);
    background: var(--ui-fill-color-blank);
    font: inherit;
    text-align: center;
}

.minigame-settings input[type='text'] {
    width: 12rem;
}

.minigame-settings input[type='number'] {
    width: 5rem;
    max-width: 100%;
    text-align: center;
}

.minigame-settings input[type='range'] {
    width: 12rem;
    max-width: 100%;
    min-width: 0;
    margin: 0;
    accent-color: var(--ui-color-primary);
}

.minigame-settings-opacity output {
    min-width: 4ch;
    text-align: right;
    font-variant-numeric: tabular-nums;
}

.minigame-settings input:focus-visible {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: 1px;
}
</style>
