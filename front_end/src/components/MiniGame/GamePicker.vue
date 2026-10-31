<template>
    <nav class="minigame-picker" :aria-label="t('minigame.title')">
        <BaseButton v-for="game in trainingGames" :key="game" :type="modelValue === game ? 'primary' : 'default'" :aria-pressed="modelValue === game" :data-cy="`game-${game}`" @click="emit('update:modelValue', game)">
            {{ t(`minigame.${game}`) }}
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
const { t } = useI18n();
</script>

<style scoped>
.minigame-picker {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.5rem;
}
</style>
