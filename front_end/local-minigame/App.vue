<template>
    <main class="offline-minigame">
        <GamePicker v-model="game" />
        <LeftClickTraining v-if="game === 'left-click' || game === 'multi-touch'" :key="game" :game-type="game" offline />
        <FlagChordTraining v-else-if="game === 'flag-chord'" offline />
        <MissingCellTraining v-else offline />
        <GameSettings />
        <HistoryMigration :progress="minigameHistoryMigration" />
        <div class="offline-controls">
            <span class="text text-small">{{ t('local.offline') }} · v{{ version.version }}</span>
            <BaseButton size="small" data-cy="offline-language" @click="toggleLanguage">
                {{ locale.startsWith('zh') ? 'English' : '中文' }}
            </BaseButton>
            <label>{{ t('local.theme') }}
                <select v-model="colorMode" data-cy="offline-theme">
                    <option value="auto">{{ t('local.auto') }}</option>
                    <option value="light">{{ t('local.light') }}</option>
                    <option value="dark">{{ t('local.dark') }}</option>
                </select>
            </label>
        </div>
        <details>
            <summary>{{ t('local.usage') }}</summary>
            <pre>{{ readme }}</pre>
        </details>
        <details>
            <summary>{{ t('local.copyright') }}</summary>
            <pre>{{ copyright }}</pre>
        </details>
    </main>
</template>

<script setup lang="ts">
import { useColorMode } from '@vueuse/core';
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import copyright from './COPYRIGHT.txt?raw';
import readme from './README.txt?raw';
import version from './version.json';

import BaseButton from '@/components/common/BaseButton.vue';
import GamePicker from '@/components/MiniGame/GamePicker.vue';
import HistoryMigration from '@/components/MiniGame/HistoryMigration.vue';
import GameSettings from '@/components/MiniGame/Settings.vue';
import type { TrainingGame } from '@/utils/minigame/games';
import { minigameHistoryMigration } from '@/utils/minigame/history';
import FlagChordTraining from '@/views/MiniGameView/FlagChordTraining/App.vue';
import LeftClickTraining from '@/views/MiniGameView/LeftClickTraining/App.vue';
import MissingCellTraining from '@/views/MiniGameView/MissingCellTraining/App.vue';

const colorMode = useColorMode({ storageKey: 'offline-minigame-color-mode', emitAuto: true });
const game = ref<TrainingGame>('left-click');
const { locale } = useI18n({ useScope: 'global' });
watch(locale, (language) => {
    document.documentElement.lang = language;
}, { immediate: true });

function toggleLanguage() {
    locale.value = locale.value.startsWith('zh') ? 'en' : 'zh-cn';
}

const i18nMessages = {
    'zh-cn': { local: {
        offline: '小游戏离线版',
        theme: '主题',
        auto: '跟随系统',
        light: '浅色',
        dark: '深色',
        usage: '使用说明',
        copyright: '版权与许可',
    } },
    en: { local: {
        offline: 'Offline minigames',
        theme: 'Theme',
        auto: 'System',
        light: 'Light',
        dark: 'Dark',
        usage: 'Usage',
        copyright: 'Copyright and licenses',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style>
body {
    margin: 0;
    background: var(--ui-bg-color);
    font-family: system-ui, sans-serif;
}
</style>

<style scoped>
.offline-minigame {
    display: grid;
    gap: 0.75rem;
    min-width: 0;
    padding: 1rem;
}

.offline-controls,
.offline-controls label {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
}

.offline-controls select {
    padding: 0.25rem;
    border: 1px solid var(--ui-border-color);
    border-radius: 0;
    color: var(--ui-text-color-regular);
    background: var(--ui-fill-color-blank);
    font: inherit;
}

.offline-controls {
    justify-content: center;
}

details {
    min-width: 0;
}

summary {
    cursor: pointer;
    text-align: center;
}

pre {
    max-width: 80ch;
    margin-inline: auto;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font: inherit;
}
</style>
