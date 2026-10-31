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
import { getMinigameDatabase, MINIGAME_RESULTS_STORE } from '@/utils/minigame/history';
import { readMinigameHistoryReplay, rebuildMinigameReplay } from '@/utils/minigame/review';
import type { MinigameReplay } from '@/utils/minigame/review';

const props = defineProps({ game: { type: String as PropType<TrainingGame>, required: true } });
defineSlots<{ default: (props: { replay: MinigameReplay | null }) => VNode[] }>();
const route = useRoute();
const loading = ref(false);
const error = ref<'invalidLink' | 'notFound' | 'localNotFound' | 'loadFailed' | 'corrupt' | null>(null);
const data = shallowRef<MinigameReplay | null>(null);

watch([() => props.game, () => route.query.player, () => route.query.key, () => route.query.history], async ([game, player, key, history], _previous, onCleanup) => {
    const controller = new AbortController();
    onCleanup(() => {
        controller.abort();
    });
    data.value = null;
    error.value = null;
    loading.value = false;
    if (player === undefined && key === undefined && history === undefined) return;
    const local = history !== undefined;
    const id = local ? history : player;
    const recordId = typeof id === 'string' && (/^\d+$/).test(id) ? Number(id) : NaN;
    if (!Number.isSafeInteger(recordId) || recordId <= 0 || (local ? player !== undefined || key !== undefined : typeof key !== 'string' || key.length === 0)) {
        error.value = 'invalidLink';
        return;
    }
    loading.value = true;
    let received = false;
    try {
        if (local) {
            const db = await getMinigameDatabase();
            const entry = await db.get(MINIGAME_RESULTS_STORE, recordId);
            if (controller.signal.aborted) return;
            if (entry === undefined) {
                error.value = 'localNotFound';
                return;
            }
            if (entry.game !== game) {
                error.value = 'invalidLink';
                return;
            }
            received = true;
            const replay = await readMinigameHistoryReplay(entry);
            if (!controller.signal.aborted) data.value = replay;
            return;
        }
        const { archive, scoreMs } = await fetchMinigameReplay(game, key as string, recordId, controller.signal);
        received = true;
        if (controller.signal.aborted) return;
        const source = await unpackReplayArchive(archive);
        if (!controller.signal.aborted) data.value = rebuildMinigameReplay(game, `${game}-${key as string}`, source, scoreMs);
    } catch (cause) {
        if (!controller.signal.aborted) error.value = isAxiosError(cause) && cause.response?.status === 404 ? 'notFound' : received ? 'corrupt' : 'loadFailed';
    } finally {
        if (!controller.signal.aborted) loading.value = false;
    }
}, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: {
        loading: '正在加载录像…',
        invalidLink: '录像链接参数无效。',
        notFound: '未找到该玩家在此榜单的录像。',
        localNotFound: '未找到该本地录像。此链接只在保存它的浏览器中有效。',
        loadFailed: '录像加载失败，请稍后重试。',
        corrupt: '录像损坏，无法播放。',
    } },
    en: { local: {
        loading: 'Loading replay…',
        invalidLink: 'Invalid replay link parameters.',
        notFound: 'No replay found for this player and ranking.',
        localNotFound: 'No local replay found. This link only works in the browser that saved it.',
        loadFailed: 'Failed to load the replay. Please try again later.',
        corrupt: 'The replay is damaged and cannot be played.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
