<!-- eslint-disable vue/no-restricted-html-elements -->
<template>
    <ElCard v-loading="loading" class="normal-tournament-card" shadow="never">
        <template #header>
            <ElLink :underline="false" href="/#/tournament">
                {{ t('local.title') }}
            </ElLink>
            &nbsp;
            <ElLink :underline="false" :disabled="loading" @click="refresh">
                <BaseIconRefresh />
            </ElLink>
        </template>
        <table v-if="tournaments.length > 0" class="normal-tournament-table">
            <tbody>
                <tr v-for="(tournament, index) in tournaments" :key="tournament.id">
                    <td class="normal-tournament-name">
                        <ElLink :underline="false" :href="`/#/tournament/${tournament.id}`">
                            {{ tournament.getLocalName(local.language) }}
                        </ElLink>
                    </td>
                    <td>
                        <span v-if="states[index] === TournamentState.Preparing" class="text-warning">
                            {{ t(`local.${TournamentState.Preparing}`, [formatDuration(tournament.startDate!.getTime() - globalNow.getTime())]) }}
                        </span>
                        <span v-else-if="states[index] === TournamentState.Ongoing" class="text-danger">
                            {{ t(`local.${TournamentState.Ongoing}`, [formatDuration(tournament.endDate!.getTime() - globalNow.getTime())]) }}
                        </span>
                        <span v-else-if="states[index] === TournamentState.Finished" class="text-success">
                            {{ t(`local.${TournamentState.Finished}`, [formatDuration(globalNow.getTime() - tournament.endDate!.getTime())]) }}
                        </span>
                    </td>
                </tr>
            </tbody>
        </table>
        <div v-else class="text-info">
            {{ t('local.empty') }}
        </div>
    </ElCard>
</template>

<script setup lang="ts">
import { ElCard, ElLink, vLoading } from 'element-plus';
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { BaseIconRefresh } from '@/components/common/icon';
import { fetchTournamentList } from '@/services/tournamentService';
import { local } from '@/store';
import { formatSecondsAsHMS, fullDay, globalNow } from '@/utils/datetime';
import { TournamentState } from '@/utils/ms_const';
import { Tournament } from '@/utils/tournaments';

const loading = ref(false);
const tournaments = ref<Tournament[]>([]);
const states = computed(() => tournaments.value.map((tournament) => tournament.getDisplayState(globalNow.value)));

onMounted(refresh);

async function refresh() {
    loading.value = true;
    try {
        const data = await fetchTournamentList('normal');
        tournaments.value = data.map((info) => new Tournament(info));
    } finally {
        loading.value = false;
    }
}

function formatDuration(milliseconds: number): string {
    const days = Math.floor(milliseconds / fullDay);
    const seconds = Math.floor((milliseconds % fullDay) / 1000);
    const timeStr = formatSecondsAsHMS(seconds);
    return days > 0 ? `${days}d ${timeStr}` : timeStr;
}

const i18nMessages = {
    'zh-cn': { local: {
        empty: '暂无活跃比赛',
        [TournamentState.Finished]: '已结束{0}',
        [TournamentState.Ongoing]: '{0}后结束',
        [TournamentState.Preparing]: '{0}后开始',
        title: '活跃比赛',
    } },
    en: { local: {
        empty: 'No active tournaments',
        [TournamentState.Finished]: 'ended {0} ago',
        [TournamentState.Ongoing]: 'ends in {0}',
        [TournamentState.Preparing]: 'starts in {0}',
        title: 'Active Tournaments',
    } },
    es: { local: {
        empty: 'No hay torneos activos',
        [TournamentState.Finished]: 'terminó hace {0}',
        [TournamentState.Ongoing]: 'termina en {0}',
        [TournamentState.Preparing]: 'empieza en {0}',
        title: 'Torneos activos',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.normal-tournament-card {
    height: 100%;
}

.normal-tournament-table {
    border-collapse: collapse;
    width: 100%;
}

.normal-tournament-table td {
    border-bottom: 1px solid var(--ui-border-color-lighter);
    padding: 6px 4px;
}
</style>
