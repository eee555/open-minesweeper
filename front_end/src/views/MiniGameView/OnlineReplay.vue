<template>
    <p v-if="loading" role="status" class="text" data-cy="minigame-replay-loading">
        {{ t('local.loading') }}
    </p>
    <p v-else-if="error" role="alert" class="text text-danger" data-cy="minigame-replay-error">
        {{ t(`local.${error}`) }}
    </p>
    <slot v-else :replay="data" />
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { ref, shallowRef, watch } from 'vue';
import type { PropType, VNode } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import { fetchMinigameReplay } from '@/services/minigameRankingService';
import { unpackReplayArchive } from '@/utils/minigame/archive';
import type { TrainingGame } from '@/utils/minigame/games';
import { rebuildMinigameReplay } from '@/utils/minigame/review';
import type { MinigameReplay } from '@/utils/minigame/review';

const props = defineProps({ game: { type: String as PropType<TrainingGame>, required: true }, enabled: { type: Boolean, default: false } });
defineSlots<{ default: (props: { replay: MinigameReplay | null }) => VNode[] }>();
const route = useRoute();
const loading = ref(false);
const error = ref<'invalidLink' | 'notFound' | 'loadFailed' | 'corrupt' | null>(null);
const data = shallowRef<MinigameReplay | null>(null);

watch([() => props.game, () => route.query.player, () => route.query.key, () => props.enabled], async ([game, player, key, enabled], _previous, onCleanup) => {
    const controller = new AbortController();
    let active = true;
    onCleanup(() => {
        active = false;
        controller.abort();
    });
    data.value = null;
    error.value = null;
    loading.value = false;
    if (!enabled) return;
    const playerId = typeof player === 'string' && (/^\d+$/).test(player) ? Number(player) : NaN;
    if (!Number.isSafeInteger(playerId) || playerId <= 0 || typeof key !== 'string' || key.length === 0) {
        error.value = 'invalidLink';
        return;
    }
    loading.value = true;
    let received = false;
    try {
        const { archive, scoreMs } = await fetchMinigameReplay(game, key, playerId, controller.signal);
        received = true;
        if (!active) return;
        const source = await unpackReplayArchive(archive);
        if (active) data.value = rebuildMinigameReplay(game, `${game}-${key}`, source, scoreMs);
    } catch (cause) {
        if (active) error.value = isAxiosError(cause) && cause.response?.status === 404 ? 'notFound' : received ? 'corrupt' : 'loadFailed';
    } finally {
        if (active) loading.value = false;
    }
}, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: {
        loading: '正在加载录像…',
        invalidLink: '录像链接参数无效。',
        notFound: '未找到该玩家在此榜单的录像。',
        loadFailed: '录像加载失败，请稍后重试。',
        corrupt: '录像损坏，无法播放。',
    } },
    en: { local: {
        loading: 'Loading replay…',
        invalidLink: 'Invalid replay link parameters.',
        notFound: 'No replay found for this player and ranking.',
        loadFailed: 'Failed to load the replay. Please try again later.',
        corrupt: 'The replay is damaged and cannot be played.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
