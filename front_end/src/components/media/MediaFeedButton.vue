<template>
    <button type="button" class="media-text-button" :disabled="disabled" :aria-busy="sending || undefined" @click="onClick">
        <i class="pi pi-heart" aria-hidden="true" />
        <span>{{ t('media.feed') }}</span>
        <span v-if="pending > 0" class="media-feed-pending">+{{ pending }}</span>
        <span v-if="pendingLabel" class="text-secondary text-small">{{ t('media.pendingStatus') }}</span>
    </button>
</template>

<script setup lang="ts">
import 'primeicons/primeicons.css';
import { onBeforeUnmount, onDeactivated, ref } from 'vue';
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

const pending = ref(0);
const sending = ref(false);
let timer: ReturnType<typeof setTimeout> | undefined;
let retryTimer: ReturnType<typeof setTimeout> | undefined;
let lastSentAt = 0;

function schedule(delay: number): void {
    clearTimeout(timer);
    timer = setTimeout(() => {
        void attempt();
    }, delay);
}

function onClick(): void {
    if (props.disabled) return;
    pending.value += 1;
    schedule(1000);
}

async function send(count: number, isRetry: boolean): Promise<void> {
    try {
        const result = await likeMedia(props.mediaId, count);
        lastSentAt = Date.now();
        emit('feed', result);
    } catch (error) {
        httpErrorNotification(error);
        if (isRetry) return;
        pending.value += count;
        clearTimeout(retryTimer);
        retryTimer = setTimeout(() => {
            void attempt(true);
        }, 1100);
    }
}

async function attempt(isRetry = false): Promise<void> {
    if (sending.value || pending.value === 0) return;
    const elapsed = Date.now() - lastSentAt;
    if (!isRetry && elapsed < 1050) {
        schedule(1050 - elapsed);
        return;
    }
    const count = pending.value;
    pending.value = 0;
    sending.value = true;
    try {
        await send(count, isRetry);
    } finally {
        sending.value = false;
    }
}

function flush(): void {
    void attempt();
}

onBeforeUnmount(() => {
    flush();
    clearTimeout(timer);
    clearTimeout(retryTimer);
});
onDeactivated(flush);

defineExpose({ flush });

const { t } = useI18n();
</script>
