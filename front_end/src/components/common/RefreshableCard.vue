<template>
    <BaseCardNormal class="refreshable-card" :aria-busy="loading">
        <header class="refreshable-card-header">
            <h2>{{ title }}</h2>
            <BaseTextButton size="small" :disabled="loading" @click="emit('refresh')">
                {{ t('action.refresh') }}
            </BaseTextButton>
        </header>
        <slot />
    </BaseCardNormal>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

import BaseCardNormal from './BaseCardNormal.vue';
import BaseTextButton from './BaseTextButton.vue';

defineProps({
    title: { type: String, required: true },
    loading: { type: Boolean, default: false },
});
const emit = defineEmits<{ refresh: [] }>();
defineSlots<{ default?: () => unknown }>();
const { t } = useI18n();
</script>

<style scoped>
.refreshable-card {
    min-width: 0;
}
.refreshable-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}
.refreshable-card-header h2 {
    margin: 0;
    font-size: var(--ui-font-size-medium);
}
</style>
