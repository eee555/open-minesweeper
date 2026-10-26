<template>
    <aside class="minigame-ranking-panel" :aria-label="modeLabel" :aria-busy="loading" data-cy="minigame-ranking-panel">
        <BaseButton class="ranking-panel-refresh square-button" size="small" :title="t('button.refresh')" :aria-label="t('button.refresh')" :loading="loading" data-cy="minigame-ranking-refresh" @click="refresh++">
            <template #icon>
                <i class="pi pi-refresh" aria-hidden="true" />
            </template>
        </BaseButton>
        <p v-if="failed" role="alert" class="text text-danger text-small">
            {{ t('ranking.loadFailed') }}
        </p>
        <BaseTable :empty="rows.length === 0" :column-count="3" :empty-text="loading ? t('local.loading') : t('ranking.empty')">
            <template #head>
                <tr>
                    <th scope="col" class="table-col-rank">
                        #
                    </th>
                    <th scope="col" class="table-col-player">
                        {{ t('prop.player') }}
                    </th>
                    <th scope="col" class="table-col-number">
                        {{ modeLabel }}
                    </th>
                </tr>
            </template>
            <tr v-for="row in rows" :key="row.player_id" :class="{ 'current-player': row.player_id === viewerId, 'personal-position': row.separated }" :aria-current="row.player_id === viewerId ? 'true' : undefined" :data-player="row.player_id">
                <td class="table-col-rank">
                    {{ row.rank ?? '--' }}
                </td>
                <td class="table-col-player">
                    <PlayerName :user-id="row.player_id" />
                </td>
                <td class="table-col-number" :title="row.record ? toISODateTimeString(new Date(row.record.achieved_at)) : undefined">
                    <RouterLink v-if="row.record" class="link" data-cy="minigame-ranking-score" :to="{ name: `minigame-${game}`, query: { player: row.player_id, key: rankingKey.slice(game.length + 1) } }">
                        {{ ms_to_s(row.record.score) }}
                    </RouterLink>
                    <template v-else>
                        --
                    </template>
                </td>
            </tr>
        </BaseTable>
        <p v-if="!loading && !failed" class="ranking-panel-summary text text-small">
            {{ t('local.count', { count: data?.count ?? 0 }) }}
            <span v-if="viewerId !== null && !data?.player?.records[rankingKey]" data-cy="minigame-ranking-unranked"> · {{ t('local.unranked') }}</span>
        </p>
    </aside>
</template>

<script setup lang="ts">
import '@/styles/link.css';

import { computed, ref, shallowRef, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink } from 'vue-router';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import PlayerName from '@/components/PlayerName.vue';
import { fetchMinigameRankingSummary } from '@/services/minigameRankingService';
import type { MinigameRankingSummary, MinigameScore } from '@/services/minigameRankingService';
import { store } from '@/store';
import { ms_to_s } from '@/utils';
import { LoginStatus } from '@/utils/common/structInterface';
import { toISODateTimeString } from '@/utils/datetime';
import type { TrainingGame } from '@/utils/minigame/games';

const props = defineProps({
    game: { type: String as PropType<TrainingGame>, required: true },
    rankingKey: { type: String, required: true },
    revision: { type: Number, default: 0 },
});
const data = shallowRef<MinigameRankingSummary | null>(null);
const loading = ref(false);
const failed = ref(false);
const refresh = ref(0);
const viewerId = computed(() => (store.login_status === LoginStatus.IsLogin ? store.user.id : null));
const densityLabels: Record<string, string> = { 50: '1/2', 75: '3/4', 87.5: '7/8' };
const modeLabel = computed(() => {
    const [level, density] = props.rankingKey.slice(props.game.length + 1).split('-');
    return [t(`level.${level}`), densityLabels[density]].filter(Boolean).join(' · ');
});
const rows = computed(() => {
    const result: { player_id: number; rank: number | null; record: MinigameScore | null; separated: boolean }[] = (data.value?.players ?? []).map((row) => ({
        player_id: row.player_id, rank: row.rank, record: row.records[props.rankingKey] ?? null, separated: false,
    }));
    const player = data.value?.player;
    const record = player?.records[props.rankingKey];
    if (player && record && player.player_id === viewerId.value && !result.some((row) => row.player_id === player.player_id)) {
        result.push({ player_id: player.player_id, rank: record.rank, record, separated: true });
    }
    return result;
});

watch([() => props.rankingKey, () => props.revision, () => store.sessionRevision, refresh], async (_value, _old, onCleanup) => {
    const controller = new AbortController();
    onCleanup(() => {
        controller.abort();
    });
    data.value = null;
    loading.value = true;
    failed.value = false;
    try {
        const result = await fetchMinigameRankingSummary(props.rankingKey, controller.signal);
        if (!controller.signal.aborted) data.value = result;
    } catch {
        if (!controller.signal.aborted) failed.value = true;
    } finally {
        if (!controller.signal.aborted) loading.value = false;
    }
}, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: {
        loading: '正在加载排行榜…',
        count: '共 {count} 人',
        unranked: '你还未在此配置上榜',
    } },
    en: { local: {
        loading: 'Loading ranking…',
        count: '{count} players',
        unranked: 'You are not ranked in this mode yet',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.minigame-ranking-panel {
    display: grid;
    gap: 0.5rem;
    min-width: 0;
}

.ranking-panel-refresh {
    justify-self: end;
}

.ranking-panel-summary {
    margin: 0;
    text-align: center;
}

.current-player > td {
    background: var(--ui-color-primary-light-9);
}

.personal-position > td {
    border-top: 2px solid var(--ui-color-primary);
}
</style>
