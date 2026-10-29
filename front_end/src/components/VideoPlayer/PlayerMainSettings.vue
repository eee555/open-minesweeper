<template>
    <div class="player-main-settings">
        <label class="player-main-settings__row">
            <span class="text-regular">{{ t('local.cellSize') }}</span>
            <InputNumber
                v-model="config.cellSize"
                class="player-main-settings__number-input"
                :min="1" :max="48"
            />
        </label>
        <label class="checkbox">
            <input v-model="config.showProbability" class="checkbox-input" type="checkbox">
            <span>{{ t('local.showProbability') }}</span>
        </label>
        <div v-if="config.showProbability" class="player-main-settings__color-scheme">
            <ColorSchemeSetting v-model="config.probabilityColorScheme" :min="0" :max="100" />
        </div>
    </div>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import InputNumber from '@/components/common/InputNumber.vue';
import ColorSchemeSetting from '@/components/visualization/ColorSchemeSetting.vue';
import type { PiecewiseColorSchemeInterface } from '@/utils/colors';

interface PlayerMainConfig {
    cellSize: number;
    probabilityColorScheme: PiecewiseColorSchemeInterface;
    showProbability: boolean;
}

const config = defineModel({
    type: Object as PropType<PlayerMainConfig>,
    required: true,
});

const i18nMessages = {
    'zh-cn': { local: {
        cellSize: '格子边长',
        showProbability: '显示概率',
    } },
    en: { local: {
        cellSize: 'Cell Size',
        showProbability: 'Show Probability',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.player-main-settings {
    display: flex;
    flex: 0 0 auto;
    flex-direction: column;
    gap: 10px;
    width: 20rem;
    min-width: min(25%, 20rem);
    max-height: calc(100vh - 290px);
    padding: 6px 0;
    overflow: auto;
}

.player-main-settings__row {
    display: flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
}

.player-main-settings__number-input {
    width: 48px;
}

.player-main-settings__color-scheme {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
}
</style>
