<template>
    <div class="button-group upload-toolbar">
        <span class="text-regular">
            {{ t('local.selected', [selected, total]) }}
        </span>
        <BaseButton :disabled="processing || selectedNone" @click="emit('upload')">
            <BaseIconUpload />&nbsp;{{ t('common.button.upload') }}
        </BaseButton>
        <BaseButton :disabled="processing || selectedNone" @click="emit('remove')">
            <BaseIconDelete />&nbsp;{{ t('local.remove') }}
        </BaseButton>
        <BaseButton v-if="processing" :disabled="stopping" @click="stopping = true">
            {{ t('local.stop') }}
        </BaseButton>
    </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { BaseIconDelete, BaseIconUpload } from '@/components/common/icon';

const props = defineProps({
    selected: { type: Number, required: true },
    total: { type: Number, required: true },
    processing: { type: Boolean, required: true },
});

const emit = defineEmits(['upload', 'remove']);

const stopping = defineModel<boolean>('stopping');

const selectedNone = computed(() => props.selected === 0);

watch(() => props.processing, (processing) => {
    if (!processing) stopping.value = false;
}, { immediate: true });

/* 本地化 Localization */
const i18nMessages = {
    'zh-cn': { local: {
        selected: '已选中：{0} / {1}',
        remove: '移除',
        stop: '停止上传',
    } },
    en: { local: {
        selected: 'Selected: {0} / {1}',
        remove: 'Remove',
        stop: 'Stop',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.upload-toolbar {
    flex-wrap: wrap;
    align-items: center;
    margin-top: 8px;
}
</style>
