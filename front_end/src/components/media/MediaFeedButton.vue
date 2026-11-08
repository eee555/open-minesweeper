<template>
    <button type="button" class="media-text-button" :disabled="disabled || sending" :aria-busy="sending || undefined" @click="onClick">
        <i class="pi pi-heart" aria-hidden="true" />
        <span>{{ t('media.feed') }}</span>
        <span v-if="pendingLabel" class="text-secondary text-small">{{ t('media.pendingStatus') }}</span>
    </button>
</template>

<script setup lang="ts">
import 'primeicons/primeicons.css';
import { onBeforeUnmount, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { httpErrorNotification } from '@/components/Notifications';
import { likeMedia } from '@/services/mediaService';
import type { MediaLikeResult } from '@/services/mediaService';

import '@/components/media/media.css';

const props = defineProps({
    mediaId: { type: Number, required: true },
    disabled: { type: Boolean, default: false },
    pendingLabel: { type: Boolean, default: false },
});
const emit = defineEmits<{ feed: [result: MediaLikeResult] }>();

const sending = ref(false);
let cooldownTimer: ReturnType<typeof setTimeout> | undefined;
let sentAt = 0;

function onClick(): void {
    if (props.disabled || sending.value) return;
    void send();
}

async function send(): Promise<void> {
    sending.value = true;
    sentAt = Date.now();
    try {
        emit('feed', await likeMedia(props.mediaId));
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        // 服务端 /like 限流 1/s；按钮至少禁用 1050ms，避免连点撞限流。
        clearTimeout(cooldownTimer);
        cooldownTimer = setTimeout(() => {
            sending.value = false;
        }, Math.max(0, 1050 - (Date.now() - sentAt)));
    }
}

onBeforeUnmount(() => {
    clearTimeout(cooldownTimer);
});

const { t } = useI18n();
</script>
