<template>
    <section class="minigame-ranking">
        <div class="ranking-toolbar">
            <ElSelect v-model="selectedGame" class="ranking-selector" :aria-label="t('local.game')">
                <ElOption v-for="game in trainingGames" :key="game" :value="game" :label="t(`local.${game}`)" />
            </ElSelect>
            <RouterLink class="link text-primary" data-cy="minigame-play-link" :to="{ name: `minigame-${selectedGame}` }">
                {{ t('local.playGame') }}
            </RouterLink>
            <div class="ranking-actions">
                <BaseButton class="square-button" data-cy="minigame-ranking-color" disabled :aria-label="t('local.color')" :title="t('local.colorPending')">
                    <i class="pi pi-palette" aria-hidden="true" />
                </BaseButton>
                <BaseButton class="square-button" data-cy="minigame-ranking-refresh" :disabled="!ranking" :aria-label="t('common.action.refresh')" :title="t('common.action.refresh')" @click="ranking?.refresh()">
                    <BaseIconRefresh :loading="ranking?.loading ?? false" aria-hidden="true" />
                </BaseButton>
            </div>
        </div>
        <RouterView v-slot="{ Component }">
            <component :is="Component" :key="selectedGame" ref="ranking" :color-scheme="colorScheme" />
        </RouterView>
    </section>
</template>

<script setup lang="ts">
import '@/styles/link.css';

import { ElOption, ElSelect } from 'element-plus';
import { computed, useTemplateRef } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';

import BaseButton from '@/components/common/BaseButton.vue';
import { BaseIconRefresh } from '@/components/common/icon';
import type { MinigameColorScheme } from '@/services/minigameRankingService';
import { trainingGames } from '@/utils/minigame/games';
import type { TrainingGame } from '@/utils/minigame/games';

defineProps({ colorScheme: { type: Function as PropType<MinigameColorScheme>, default: undefined } });
const route = useRoute();
const router = useRouter();
const ranking = useTemplateRef<{ refresh: () => Promise<void>; loading: boolean }>('ranking');
const selectedGame = computed<TrainingGame>({
    get: () => trainingGames.find((game) => route.name === `ranking_minigame_${game}`) ?? 'left-click',
    set: (game) => {
        void router.push({ name: `ranking_minigame_${game}` });
    },
});

const i18nMessages = {
    'zh-cn': { local: {
        game: '小游戏',
        'left-click': '左键训练',
        'multi-touch': '多指训练',
        'flag-chord': '标双训练',
        'missing-cell': '漏雷训练',
        playGame: '前往小游戏',
        color: '颜色',
        colorPending: '配色待开放',
    } },
    en: { local: {
        game: 'Minigame',
        'left-click': 'Left-click training',
        'multi-touch': 'Multi-touch training',
        'flag-chord': 'Flag-and-chord training',
        'missing-cell': 'Missing cell training',
        playGame: 'Play game',
        color: 'Color',
        colorPending: 'Colors coming later',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.minigame-ranking {
    min-width: 0;
}

.ranking-toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
}

.ranking-selector {
    width: 14rem;
}

.ranking-actions {
    display: flex;
    gap: 0.5rem;
    margin-left: auto;
}
</style>
