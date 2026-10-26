<template>
    <div class="minigame-view">
        <GamePicker v-model="selected" />
        <BaseButton v-show="!showRanking" class="minigame-ranking-toggle square-button" :style="{ top: `${drawerTop + 8}px` }" :title="t('local.showRanking')" :aria-label="t('local.showRanking')" :aria-expanded="showRanking" :aria-controls="rankingDrawerId" data-cy="minigame-ranking-toggle" @click="showRanking = true">
            <i class="pi pi-bookmark" aria-hidden="true" />
        </BaseButton>
        <OnlineReplay v-slot="{ replay }" :enabled="viewingReplay" :game="selected">
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
        </OnlineReplay>
        <ElDrawer :id="rankingDrawerId" v-model="showRanking" :title="t('local.ranking')" direction="rtl" size="min(100vw, 24rem)" :style="{ top: `${drawerTop}px`, height: `calc(100% - ${drawerTop}px)`, '--el-drawer-padding-primary': '12px' }" :modal="false" modal-penetrable :lock-scroll="false" :close-on-click-modal="false" aria-modal="false" append-to-body destroy-on-close>
            <RankingPanel v-if="showRanking && currentRankingKey" :game="selected" :ranking-key="currentRankingKey" :revision="rankingRevision" />
            <template #footer>
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

import OnlineReplay from './OnlineReplay.vue';
import RankingPanel from './RankingPanel.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import GamePicker from '@/components/MiniGame/GamePicker.vue';
import HistoryMigration from '@/components/MiniGame/HistoryMigration.vue';
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
const viewingReplay = computed(() => route.query.player !== undefined || route.query.key !== undefined);
const selected = computed<TrainingGame>({
    get: () => trainingGames.find((game) => route.name === `minigame-${game}`) ?? 'left-click',
    set: (game) => {
        void router.push(`/minigame/${game}`);
    },
});
const pendingResult = shallowRef<{ rankingKey: string; scoreMs: number; replay: MinigameReplayData } | null>(null);
const submitting = ref(false);
const uploaded = ref(false);
const showRanking = ref(false);
const rankingDrawerId = `minigame-ranking-${useId()}`;
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

function resetGame() {
    clearResult();
    if (!viewingReplay.value) return;
    const query = { ...route.query };
    delete query.player;
    delete query.key;
    void router.replace({ query });
}

watch([() => route.name, () => route.query.player, () => route.query.key], clearResult);

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

.minigame-ranking-toggle {
    position: fixed;
    right: 0;
    z-index: 1;
    border-right: 0;
    color: var(--ui-color-primary);
}

.minigame-result-actions {
    display: flex;
    justify-content: center;
}
</style>
