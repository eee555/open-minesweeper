<template>
    <section class="card" data-cy="minigame-settings-section">
        <h2 class="card-title">
            {{ t('minigame.title') }}
        </h2>
        <MiniGameSettings description-layout />
    </section>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import { useI18n } from 'vue-i18n';

import MiniGameSettings from '@/components/MiniGame/Settings.vue';

const { t } = useI18n();
</script>
