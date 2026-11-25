<template>
    <article class="card media-card" :data-cy="`media-card-${media.id}`">
        <div class="media-card-head">
            <MediaSourceLink class="media-card-title" :format="media.format" :suffix="media.suffix">
                {{ media.title || t('media.titleMissing') }}
            </MediaSourceLink>
            <span v-if="showStatus" class="media-card-status" :class="`media-card-status--${media.status}`">{{ statusLabel }}</span>
            <span v-if="media.metadata_pending" class="media-card-status media-card-status--pending">{{ t('media.titleMissing') }}</span>
        </div>
        <div class="media-card-meta">
            <span class="text-secondary text-small">{{ t('media.author') }}: <PlayerName :user-id="media.user_id" /></span>
            <span class="text-secondary text-small">{{ t('media.publishedAt') }}: {{ formatDate(media.created_at) }}</span>
            <span class="text-secondary text-small">{{ t('media.language') }}: {{ languageLabel }}</span>
        </div>
        <div class="media-card-stats">
            <span>{{ t('media.likesCount') }}: {{ currentLikes }}</span>
            <span>{{ t('media.hotNow') }}: {{ formatHeat(currentHot) }}</span>
            <MediaFeedButton
                v-if="showFeed" :media-id="media.id" :disabled="feedDisabled" :balance="feedBalance"
                :pending-label="media.status === 'pending'" @feed="onFeed"
            />
            <MediaEmbed v-if="embedUrl" :src="embedUrl" />
        </div>
        <div v-if="showRejectInfo && media.status === 'rejected'" class="media-card-reject">
            <span>{{ t('media.rejectReason') }}: {{ media.reject_reason }}</span>
            <span v-if="media.rejected_by">{{ t('media.rejectedBy') }}: <PlayerName :user-id="media.rejected_by" /></span>
        </div>
    </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import MediaEmbed from './MediaEmbed.vue';
import MediaFeedButton from './MediaFeedButton.vue';
import MediaSourceLink from './MediaSourceLink.vue';

import PlayerName from '@/components/PlayerName.vue';
import type { MediaItem, MediaLikeResult } from '@/services/mediaService';
import { mediaEmbedUrl, mediaLanguageLabel } from '@/utils/media';

import '@/components/media/media.css';

const props = defineProps({
    media: { type: Object as PropType<MediaItem>, required: true },
    showStatus: { type: Boolean, default: false },
    showRejectInfo: { type: Boolean, default: false },
    showFeed: { type: Boolean, default: true },
    feedDisabled: { type: Boolean, default: false },
    feedBalance: { type: Number as PropType<number | null>, default: null },
});
const emit = defineEmits<{ feed: [result: MediaLikeResult] }>();

const { t } = useI18n();

const currentLikes = ref(props.media.likes);
const currentHot = ref(props.media.hot_now);
const embedUrl = computed(() => mediaEmbedUrl(props.media.format, props.media.suffix));
watch(() => props.media, (media) => {
    currentLikes.value = media.likes;
    currentHot.value = media.hot_now;
});

const statusLabel = computed(() => t({
    pending: 'media.pendingStatus',
    verified: 'media.verifiedStatus',
    rejected: 'media.rejectedStatus',
}[props.media.status]));
const languageLabel = computed(() => mediaLanguageLabel(props.media.language) || t('media.unknownLanguage'));

function formatDate(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function formatHeat(value: number): string {
    return value.toFixed(2);
}

function onFeed(result: MediaLikeResult): void {
    currentLikes.value = result.likes;
    currentHot.value = result.hot_now;
    emit('feed', result);
}
</script>
