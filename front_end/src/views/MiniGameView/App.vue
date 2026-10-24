<template>
    <div class="minigame-view">
        <div class="minigame-navigation">
            <GamePicker v-model="selected" />
            <RouterLink class="link text-primary" data-cy="minigame-ranking-link" :to="{ name: `ranking_minigame_${selected}` }">
                {{ t('local.ranking') }}
            </RouterLink>
        </div>
        <RouterView v-slot="{ Component }">
            <component :is="Component" @completed="submitResult" />
        </RouterView>
        <GameSettings />
        <HistoryMigration :progress="minigameHistoryMigration" />
    </div>
</template>

<script setup lang="ts">
import '@/styles/link.css';

import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';

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
async function submitResult(rankingKey: string, scoreMs: number, replay: MinigameReplayData) {
    if (store.login_status !== LoginStatus.IsLogin || store.user.is_banned) return;
    try {
        await submitMinigameScore(rankingKey, scoreMs, replay);
    } catch (error) {
        httpErrorNotification(error);
    }
}

const selected = computed<TrainingGame>({
    get: () => trainingGames.find((game) => route.name === `minigame-${game}`) ?? 'left-click',
    set: (game) => {
        void router.push(`/minigame/${game}`);
    },
});

const i18nMessages = {
    'zh-cn': { local: { ranking: '排行榜' } },
    en: { local: { ranking: 'Rankings' } },
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
</style>
