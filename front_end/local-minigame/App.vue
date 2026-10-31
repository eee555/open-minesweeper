<template>
    <main class="offline-minigame">
        <GamePicker :model-value="game" @update:model-value="selectGame" />
        <BaseButton v-show="!showHistory" class="offline-history-toggle square-button" :title="t('local.history')" :aria-label="t('local.history')" :aria-expanded="showHistory" :aria-controls="historyDrawerId" data-cy="minigame-history-toggle" @click="showHistory = true">
            <i class="pi pi-history" aria-hidden="true" />
        </BaseButton>
        <p v-if="loadingReplay" role="status" class="text" data-cy="minigame-replay-loading">
            {{ t('local.loading') }}
        </p>
        <p v-if="replayError" role="alert" class="text text-danger" data-cy="minigame-replay-error">
            {{ t(`local.${replayError}`) }}
        </p>
        <div class="offline-game" :inert="loadingReplay">
            <LeftClickTraining v-if="game === 'left-click' || game === 'multi-touch'" :key="game" :game-type="game" :replay-data="replay?.game === 'left-click' || replay?.game === 'multi-touch' ? replay : null" offline @reset="resetReplay" @ranking-change="selectedRankingKey = $event" />
            <FlagChordTraining v-else-if="game === 'flag-chord'" :replay-data="replay?.game === 'flag-chord' ? replay : null" offline @reset="resetReplay" @ranking-change="selectedRankingKey = $event" />
            <MissingCellTraining v-else :replay-data="replay?.game === 'missing-cell' ? replay : null" offline @reset="resetReplay" @ranking-change="selectedRankingKey = $event" />
        </div>
        <ElConfigProvider :locale="locale.startsWith('zh') ? zhCn : en">
            <ElDrawer :id="historyDrawerId" v-model="showHistory" :title="t('local.history')" direction="rtl" size="min(100vw, 24rem)" :style="{ '--el-drawer-padding-primary': '12px' }" :modal="false" modal-penetrable :lock-scroll="false" :close-on-click-modal="false" aria-modal="false" append-to-body destroy-on-close>
                <HistoryPanel v-if="showHistory && currentRankingKey" :ranking-key="currentRankingKey" @play="playHistory" />
            </ElDrawer>
        </ElConfigProvider>
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
import { ElConfigProvider, ElDrawer } from 'element-plus';
import en from 'element-plus/es/locale/lang/en';
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import { computed, onBeforeUnmount, ref, shallowRef, useId, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import copyright from './COPYRIGHT.txt?raw';
import readme from './README.txt?raw';
import version from './version.json';

import BaseButton from '@/components/common/BaseButton.vue';
import GamePicker from '@/components/MiniGame/GamePicker.vue';
import HistoryMigration from '@/components/MiniGame/HistoryMigration.vue';
import HistoryPanel from '@/components/MiniGame/HistoryPanel.vue';
import GameSettings from '@/components/MiniGame/Settings.vue';
import type { TrainingGame } from '@/utils/minigame/games';
import { getMinigameDatabase, MINIGAME_RESULTS_STORE, minigameHistoryMigration } from '@/utils/minigame/history';
import type { MinigameHistoryMetadata } from '@/utils/minigame/history';
import { readMinigameHistoryReplay } from '@/utils/minigame/review';
import type { MinigameReplay } from '@/utils/minigame/review';
import FlagChordTraining from '@/views/MiniGameView/FlagChordTraining/App.vue';
import LeftClickTraining from '@/views/MiniGameView/LeftClickTraining/App.vue';
import MissingCellTraining from '@/views/MiniGameView/MissingCellTraining/App.vue';

const colorMode = useColorMode({ storageKey: 'offline-minigame-color-mode', emitAuto: true });
const game = ref<TrainingGame>('left-click');
const selectedRankingKey = ref('');
const currentRankingKey = computed(() => (selectedRankingKey.value.startsWith(`${game.value}-`) ? selectedRankingKey.value : null));
const showHistory = ref(false);
const historyDrawerId = `minigame-history-${useId()}`;
const replay = shallowRef<MinigameReplay | null>(null);
const loadingReplay = ref(false);
const replayError = ref<'notFound' | 'loadFailed' | 'corrupt' | null>(null);
let replayRequest = 0;

function resetReplay() {
    replayRequest++;
    replay.value = null;
    loadingReplay.value = false;
    replayError.value = null;
}

function selectGame(value: TrainingGame) {
    resetReplay();
    game.value = value;
}

async function playHistory(entry: MinigameHistoryMetadata) {
    const request = ++replayRequest;
    loadingReplay.value = true;
    replayError.value = null;
    let received = false;
    try {
        const db = await getMinigameDatabase();
        const stored = await db.get(MINIGAME_RESULTS_STORE, entry.id);
        if (request !== replayRequest) return;
        if (stored === undefined) {
            replayError.value = 'notFound';
            return;
        }
        received = true;
        const data = await readMinigameHistoryReplay(stored);
        if (request === replayRequest) replay.value = data;
    } catch {
        if (request === replayRequest) replayError.value = received ? 'corrupt' : 'loadFailed';
    } finally {
        if (request === replayRequest) loadingReplay.value = false;
    }
}

onBeforeUnmount(() => {
    replayRequest++;
});
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
        history: '本地历史',
        loading: '正在加载录像…',
        notFound: '未找到该本地录像。',
        loadFailed: '录像加载失败，请重试。',
        corrupt: '录像损坏，无法播放。',
        theme: '主题',
        auto: '跟随系统',
        light: '浅色',
        dark: '深色',
        usage: '使用说明',
        copyright: '版权与许可',
    } },
    en: { local: {
        offline: 'Offline minigames',
        history: 'Local history',
        loading: 'Loading replay…',
        notFound: 'No local replay found.',
        loadFailed: 'Failed to load the replay. Please try again.',
        corrupt: 'The replay is damaged and cannot be played.',
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

.offline-history-toggle {
    position: fixed;
    top: 8px;
    right: 0;
    z-index: 1;
    border-right: 0;
    color: var(--ui-color-primary);
}

.offline-game {
    min-width: 0;
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
