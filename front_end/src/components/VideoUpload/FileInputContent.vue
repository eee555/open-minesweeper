<template>
    <span v-if="isUserAnonymous" class="text-large text-regular">
        {{ t('msg.realNameRequired') }}
    </span>
    <template v-else>
        <span class="text-large" style="padding: 0.1em; color: inherit;">
            {{ t('local.dragOrClick') }}
        </span>
        <span class="text-regular text-small" style="padding: 0.1em;">
            {{ t('local.constraintSize') }}
        </span>
    </template>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

defineProps({
    isUserAnonymous: { type: Boolean, default: true },
});

/* 本地化 Localization */
const i18nMessages = {
    'zh-cn': { local: {
        dragOrClick: '将录像拉到此处或点击此处选择',
        constraintSize: '*单个文件大小不能超过5MB',
    } },
    en: { local: {
        dragOrClick: 'Drag files here or click here to select',
        constraintSize: '*File size maximum is 5MB.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
