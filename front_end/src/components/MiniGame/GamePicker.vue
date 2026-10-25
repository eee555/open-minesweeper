<template>
    <nav class="minigame-picker" :aria-label="t('local.games')">
        <BaseButton v-for="game in trainingGames" :key="game" :type="modelValue === game ? 'primary' : 'default'" :aria-pressed="modelValue === game" :data-cy="`game-${game}`" @click="emit('update:modelValue', game)">
            {{ t(`local.${game}`) }}
        </BaseButton>
    </nav>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { trainingGames } from '@/utils/minigame/games';
import type { TrainingGame } from '@/utils/minigame/games';

defineProps({ modelValue: { type: String as PropType<TrainingGame>, required: true } });
const emit = defineEmits<{ 'update:modelValue': [game: TrainingGame] }>();
const i18nMessages = {
    'zh-cn': { local: {
        games: '小游戏',
        'left-click': '左键训练',
        'multi-touch': '多指训练',
        'flag-chord': '标双训练',
        'missing-cell': '漏雷训练',
    } },
    en: { local: {
        games: 'Minigames',
        'left-click': 'Left-click training',
        'multi-touch': 'Multi-touch training',
        'flag-chord': 'Flag-and-chord training',
        'missing-cell': 'Missing cell training',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.minigame-picker {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.5rem;
}
</style>
