<template>
    <Teleport to="body">
        <dialog v-if="progress !== null" ref="dialog" class="history-migration" :aria-label="t('local.message')" aria-busy="true" closedby="none" data-cy="minigame-history-migration" @cancel.prevent @keydown.stop>
            <p class="text text-medium" role="status">
                {{ t('local.message') }}
            </p>
            <progress :value="progress.completed" :max="progress.total" :aria-label="t('local.message')" />
            <output aria-live="polite">{{ progress.completed }} / {{ progress.total }}</output>
        </dialog>
    </Teleport>
</template>

<script setup lang="ts">
import { useTemplateRef, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { HistoryMigrationProgress } from '@/utils/minigame/history';

defineProps({ progress: { type: Object as PropType<HistoryMigrationProgress | null>, default: null } });
const dialog = useTemplateRef('dialog');
watch(dialog, (element, previous) => {
    previous?.close();
    element?.showModal();
}, { flush: 'post' });

const i18nMessages = {
    'zh-cn': { local: { message: '正在优化录像格式，请不要关闭页面' } },
    en: { local: { message: 'Optimizing replay format. Please do not close this page.' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.history-migration {
    width: min(28rem, calc(100vw - 32px));
    box-sizing: border-box;
    padding: 12px;
    border: 1px solid var(--ui-border-color);
    color: var(--ui-text-color-regular);
    background: var(--ui-bg-color);
    text-align: center;
}

.history-migration::backdrop {
    background: rgb(0 0 0 / 40%);
}

.history-migration p {
    margin: 0;
}

.history-migration progress {
    display: block;
    width: 100%;
    margin: 12px 0 4px;
    accent-color: var(--ui-color-primary);
}
</style>
