<template>
    <section class="minigame-ranking">
        <div class="ranking-toolbar">
            <select v-model="selectedGame" class="base-select ranking-selector" :aria-label="t('local.game')">
                <option v-for="game in trainingGames" :key="game" :value="game">
                    {{ t(`minigame.${game}`) }}
                </option>
            </select>
            <RouterLink class="link text-primary" data-cy="minigame-play-link" :to="{ name: `minigame-${selectedGame}` }">
                {{ t('local.playGame') }}
            </RouterLink>
            <div class="ranking-actions">
                <BaseButton class="square-button" data-cy="minigame-ranking-color" :type="local.colored ? 'primary' : 'default'" :aria-label="t('prop.color')" :title="t('prop.color')" :aria-pressed="local.colored" @click="local.colored = !local.colored">
                    <i class="pi pi-palette ranking-color-icon" aria-hidden="true" />
                </BaseButton>
                <BaseButton class="square-button" data-cy="minigame-ranking-refresh" :disabled="!ranking" :aria-label="t('action.refresh')" :title="t('action.refresh')" @click="ranking?.refresh()">
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

import { computed, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';

import BaseButton from '@/components/common/BaseButton.vue';
import { BaseIconRefresh } from '@/components/common/icon';
import type { MinigameColorScheme } from '@/services/minigameRankingService';
import { colorThemes } from '@/store/color';
import { local } from '@/store/local';
import { trainingGames } from '@/utils/minigame/games';
import type { TrainingGame } from '@/utils/minigame/games';
import { minigameCes } from '@/utils/minigame/scoreDisplay';
import { getPiecewiseColorSchemeName } from '@/utils/ms_const';

const route = useRoute();
const router = useRouter();
const ranking = useTemplateRef<{ refresh: () => Promise<void>; loading: boolean }>('ranking');
const selectedGame = computed<TrainingGame>({
    get: () => trainingGames.find((game) => route.name === `ranking_minigame_${game}`) ?? 'left-click',
    set: (game) => {
        void router.push({ name: `ranking_minigame_${game}` });
    },
});
const colorScheme = computed<MinigameColorScheme | undefined>(() => {
    if (!local.value.colored) return undefined;
    const theme = colorThemes[getPiecewiseColorSchemeName('ces')].value;
    return (rankingDefinition, score) => {
        if (rankingDefinition.game !== 'left-click') return undefined;
        const ces = minigameCes(score, rankingDefinition.key);
        return ces === null ? undefined : theme.getStyle(ces);
    };
});

const i18nMessages = {
    'zh-cn': { local: {
        game: '小游戏',
        playGame: '前往小游戏',
    } },
    en: { local: {
        game: 'Minigame',
        playGame: 'Play game',
    } },
    es: { local: {
        game: 'Minijuego',
        playGame: 'Jugar',
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

.ranking-color-icon {
    background: linear-gradient(135deg, #e5484d 15%, #c99700 35%, #16a34a 60%, #3b82f6 85%);
    background-clip: text;
    color: transparent;
}
</style>
