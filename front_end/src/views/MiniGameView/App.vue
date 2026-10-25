<template>
    <div class="minigame-view">
        <div class="minigame-navigation">
            <GamePicker v-model="selected" />
            <RouterLink class="link text-primary" data-cy="minigame-ranking-link" :to="{ name: `ranking_minigame_${selected}` }">
                {{ t('local.ranking') }}
            </RouterLink>
        </div>
        <OnlineReplay v-slot="{ replay }" :enabled="viewingReplay" :game="selected">
            <RouterView v-slot="{ Component }">
                <component :is="Component" :key="selected" :replay-data="replay" @completed="queueResult" @reset="resetGame">
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
        <GameSettings />
        <HistoryMigration :progress="minigameHistoryMigration" />
    </div>
</template>

<script setup lang="ts">
import '@/styles/link.css';

import { computed, ref, shallowRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';

import OnlineReplay from './OnlineReplay.vue';

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
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        submitting.value = false;
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        ranking: '排行榜',
        upload: '上传成绩与回放',
        uploading: '正在上传',
        uploaded: '已上传',
        loginRequired: '登录后可上传成绩与回放',
        banned: '封禁账号无法上传',
    } },
    en: { local: {
        ranking: 'Rankings',
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

.minigame-navigation {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: 1rem;
}

.minigame-result-actions {
    display: flex;
    justify-content: center;
}
</style>
