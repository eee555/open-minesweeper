<template>
    <div class="minigame-view">
        <GamePicker v-model="selected" />
        <div v-show="!showDrawer" class="minigame-bookmarks" :style="{ top: `${drawerTop + 8}px` }">
            <BaseButton class="square-button" :title="t('local.showRanking')" :aria-label="t('local.showRanking')" :aria-expanded="drawerContent === 'ranking'" :aria-controls="drawerId" data-cy="minigame-ranking-toggle" @click="drawerContent = 'ranking'">
                <i class="pi pi-bookmark" aria-hidden="true" />
            </BaseButton>
            <BaseButton class="square-button" :title="t('local.showHistory')" :aria-label="t('local.showHistory')" :aria-expanded="drawerContent === 'history'" :aria-controls="drawerId" data-cy="minigame-history-toggle" @click="drawerContent = 'history'">
                <i class="pi pi-history" aria-hidden="true" />
            </BaseButton>
        </div>
        <ReplayLoader v-slot="{ replay }" :game="selected">
            <RouterView v-slot="{ Component }">
                <component :is="Component" :key="selected" :replay-data="replay" @completed="queueResult" @reset="resetGame" @ranking-change="selectedRankingKey = $event">
                    <template #resultActions>
                        <div v-if="pendingResult !== null" class="minigame-result-actions">
                            <BaseButton type="primary" :loading="submitting" :disabled="!canUpload || uploaded" :title="uploadHint" data-cy="minigame-upload" @click="submitResult">
                                {{ t(submitting ? 'local.uploading' : uploaded ? 'local.uploaded' : 'local.upload') }}
                            </BaseButton>
                        </div>
                    </template>
                </component>
            </RouterView>
        </ReplayLoader>
        <ElDrawer :id="drawerId" v-model="showDrawer" :title="t(drawerContent === 'history' ? 'local.history' : 'local.ranking')" direction="rtl" size="min(100vw, 24rem)" :style="{ top: `${drawerTop}px`, height: `calc(100% - ${drawerTop}px)`, '--el-drawer-padding-primary': '12px' }" :modal="false" modal-penetrable :lock-scroll="false" :close-on-click-modal="false" aria-modal="false" append-to-body destroy-on-close>
            <template #header>
                <div class="minigame-drawer-switch">
                    <BaseButton :type="drawerContent === 'ranking' ? 'primary' : 'default'" :aria-pressed="drawerContent === 'ranking'" data-cy="minigame-drawer-ranking" @click="drawerContent = 'ranking'">
                        {{ t('local.ranking') }}
                    </BaseButton>
                    <BaseButton :type="drawerContent === 'history' ? 'primary' : 'default'" :aria-pressed="drawerContent === 'history'" data-cy="minigame-drawer-history" @click="drawerContent = 'history'">
                        {{ t('local.history') }}
                    </BaseButton>
                </div>
            </template>
            <RankingPanel v-if="drawerContent === 'ranking' && currentRankingKey" :game="selected" :ranking-key="currentRankingKey" :revision="rankingRevision" />
            <HistoryPanel v-else-if="drawerContent === 'history' && currentRankingKey" :ranking-key="currentRankingKey" @play="playHistory" />
            <template v-if="drawerContent === 'ranking'" #footer>
                <RouterLink class="link text-primary" data-cy="minigame-ranking-link" :to="{ name: `ranking_minigame_${selected}` }">
                    {{ t('local.fullRanking') }}
                </RouterLink>
            </template>
        </ElDrawer>
        <GameSettings />
        <HistoryMigration :progress="minigameHistoryMigration" />
    </div>
</template>

<script setup lang="ts">
import '@/styles/link.css';

import { useElementBounding } from '@vueuse/core';
import { ElDrawer } from 'element-plus';
import { computed, onMounted, ref, shallowRef, useId, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';

import RankingPanel from './RankingPanel.vue';
import ReplayLoader from './ReplayLoader.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import GamePicker from '@/components/MiniGame/GamePicker.vue';
import HistoryMigration from '@/components/MiniGame/HistoryMigration.vue';
import HistoryPanel from '@/components/MiniGame/HistoryPanel.vue';
import GameSettings from '@/components/MiniGame/Settings.vue';
import { httpErrorNotification } from '@/components/Notifications';
import { submitMinigameScore } from '@/services/minigameRankingService';
import { store } from '@/store';
import { LoginStatus } from '@/utils/common/structInterface';
import { trainingGames } from '@/utils/minigame/games';
import type { TrainingGame } from '@/utils/minigame/games';
import { minigameHistoryMigration } from '@/utils/minigame/history';
import type { MinigameReplayData } from '@/utils/minigame/history';

const route = useRoute();
const router = useRouter();
const viewingReplay = computed(() => route.query.player !== undefined || route.query.key !== undefined || route.query.history !== undefined);
const selected = computed<TrainingGame>({
    get: () => trainingGames.find((game) => route.name === `minigame-${game}`) ?? 'left-click',
    set: (game) => {
        void router.push(`/minigame/${game}`);
    },
});
const pendingResult = shallowRef<{ rankingKey: string; scoreMs: number; replay: MinigameReplayData } | null>(null);
const submitting = ref(false);
const uploaded = ref(false);
const drawerContent = ref<'ranking' | 'history' | null>(null);
const showDrawer = computed({ get: () => drawerContent.value !== null,
    set: (open) => {
        if (!open) drawerContent.value = null;
    } });
const drawerId = `minigame-drawer-${useId()}`;
const header = shallowRef<HTMLElement | null>(null);
onMounted(() => {
    header.value = document.querySelector<HTMLElement>('.site-header');
});
const { bottom: headerBottom } = useElementBounding(header);
const drawerTop = computed(() => Math.max(0, headerBottom.value));
const selectedRankingKey = ref('');
const currentRankingKey = computed(() => (selectedRankingKey.value.startsWith(`${selected.value}-`) ? selectedRankingKey.value : null));
const rankingRevision = ref(0);
const canUpload = computed(() => store.login_status === LoginStatus.IsLogin && !store.user.is_banned);
const uploadHint = computed(() => (store.login_status !== LoginStatus.IsLogin ? t('local.loginRequired') : store.user.is_banned ? t('local.banned') : undefined));

function queueResult(rankingKey: string, scoreMs: number, replay: MinigameReplayData) {
    pendingResult.value = { rankingKey, scoreMs, replay };
    uploaded.value = false;
}

function clearResult() {
    pendingResult.value = null;
    uploaded.value = false;
}

function playHistory(id: number) {
    void router.push({ name: `minigame-${selected.value}`, query: { history: id } });
}

function resetGame() {
    clearResult();
    if (!viewingReplay.value) return;
    const query = { ...route.query };
    delete query.player;
    delete query.key;
    delete query.history;
    void router.replace({ query });
}

watch([() => route.name, () => route.query.player, () => route.query.key, () => route.query.history], clearResult);

async function submitResult() {
    const result = pendingResult.value;
    if (result === null || submitting.value || uploaded.value || !canUpload.value) return;
    submitting.value = true;
    try {
        await submitMinigameScore(result.rankingKey, result.scoreMs, result.replay);
        if (pendingResult.value === result) uploaded.value = true;
        rankingRevision.value++;
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        submitting.value = false;
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        ranking: '排行榜',
        fullRanking: '完整排行榜',
        showRanking: '显示排行榜',
        history: '本地历史',
        showHistory: '显示本地历史',
        upload: '上传成绩与回放',
        uploading: '正在上传',
        uploaded: '已上传',
        loginRequired: '登录后可上传成绩与回放',
        banned: '封禁账号无法上传',
    } },
    en: { local: {
        ranking: 'Rankings',
        fullRanking: 'Full rankings',
        showRanking: 'Show ranking',
        history: 'Local history',
        showHistory: 'Show local history',
        upload: 'Upload score and replay',
        uploading: 'Uploading',
        uploaded: 'Uploaded',
        loginRequired: 'Log in to upload your score and replay',
        banned: 'Banned accounts cannot upload',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.minigame-view {
    display: grid;
    gap: 0.75rem;
    min-width: 0;
}

.minigame-bookmarks {
    position: fixed;
    right: 0;
    z-index: 1;
    display: grid;
    gap: 4px;
}

.minigame-bookmarks > button {
    border-right: 0;
    color: var(--ui-color-primary);
}

.minigame-drawer-switch {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
}

.minigame-result-actions {
    display: flex;
    justify-content: center;
}
</style>
