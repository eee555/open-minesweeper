<template>
    <section class="minigame-records">
        <form @submit.prevent="load">
            <label>
                {{ t('prop.userId') }}
                <ElInputNumber v-model="playerId" :min="1" :precision="0" :controls="false" :disabled="working" data-cy="minigame-player-id" />
            </label>
            <label>
                {{ t('minigame.title') }}
                <ElSelect v-model="game" :disabled="working" data-cy="minigame-game">
                    <ElOption v-for="item in trainingGames" :key="item" :value="item" :label="t(`minigame.${item}`)" />
                </ElSelect>
            </label>
            <BaseButton native-type="submit" :disabled="!validPlayer" :loading="working" data-cy="minigame-query">
                {{ t('button.query') }}
            </BaseButton>
        </form>
        <BaseTable v-if="result" :empty="rows.length === 0" :column-count="4" :empty-text="t('ranking.empty')" data-cy="minigame-records">
            <template #head>
                <tr><th>{{ t('local.rankingKey') }}</th><th>{{ t('local.score') }}</th><th>{{ t('local.achievedAt') }}</th><th /></tr>
            </template>
            <tr v-for="row in rows" :key="row.key" :data-ranking-key="row.key">
                <td>{{ row.key }}</td>
                <td>{{ ms_to_s(row.score) }}</td>
                <td>{{ toISODateTimeString(new Date(row.achieved_at)) }}</td>
                <td>
                    <BaseButton type="danger" :disabled="working" data-cy="minigame-delete" @click="remove(row.key)">
                        {{ t('button.delete') }}
                    </BaseButton>
                </td>
            </tr>
        </BaseTable>
    </section>
</template>

<script setup lang="ts">
import { ElInputNumber, ElMessageBox, ElOption, ElSelect } from 'element-plus';
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { actionSuccessNotification, httpErrorNotification } from '@/components/Notifications';
import $axios from '@/http';
import type { MinigameScore } from '@/services/minigameRankingService';
import { ms_to_s } from '@/utils';
import { toISODateTimeString } from '@/utils/datetime';
import { trainingGames } from '@/utils/minigame/games';
import type { TrainingGame } from '@/utils/minigame/games';

const playerId = ref<number>();
const game = ref<TrainingGame>('left-click');
const working = ref(false);
interface PlayerRecords { player_id: number; records: Record<string, MinigameScore | null> }
const result = ref<PlayerRecords>();
const validPlayer = computed(() => playerId.value !== undefined && Number.isSafeInteger(playerId.value) && playerId.value > 0);
const rows = computed(() => Object.entries(result.value?.records ?? {}).flatMap(([key, record]) => (record ? [{ key, ...record }] : [])));

watch([playerId, game], () => {
    result.value = undefined;
});

async function load() {
    if (!validPlayer.value || working.value) return;
    working.value = true;
    result.value = undefined;
    try {
        const { data } = await $axios.get<PlayerRecords>(`/api/minigame/${game.value}/player/${playerId.value}`);
        result.value = data;
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        working.value = false;
    }
}

async function remove(rankingKey: string) {
    if (!result.value || working.value) return;
    const player = result.value.player_id;
    working.value = true;
    try {
        await ElMessageBox.confirm(t('local.confirmDelete', { player, key: rankingKey }), t('button.delete'), { type: 'warning' });
        await $axios.delete(`/api/minigame/admin/${rankingKey}/player/${player}`);
        result.value.records[rankingKey] = null;
        actionSuccessNotification();
    } catch (error) {
        if (error !== 'cancel' && error !== 'close') httpErrorNotification(error);
    } finally {
        working.value = false;
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        rankingKey: '榜单 key',
        score: '用时（秒）',
        achievedAt: '达成时间',
        confirmDelete: '删除玩家 {player} 在 {key} 的最佳成绩及对应回放？',
    } },
    en: { local: {
        rankingKey: 'Ranking key',
        score: 'Time (seconds)',
        achievedAt: 'Achieved at',
        confirmDelete: 'Delete player {player}\'s best score and replay for {key}?',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.minigame-records {
    display: grid;
    gap: 8px;
}

form {
    display: flex;
    align-items: end;
    flex-wrap: wrap;
    gap: 8px;
}

label {
    display: grid;
    gap: 4px;
    width: 220px;
    max-width: 100%;
}
</style>
