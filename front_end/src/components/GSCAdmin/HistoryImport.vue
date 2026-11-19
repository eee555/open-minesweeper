<template>
    <h3>{{ t('local.historyTitle') }}</h3>
    <p>{{ t('local.historyHint') }}</p>
    <BaseButton :loading="loading" :disabled="order <= 0" data-cy="history-refresh" @click="refresh">
        {{ t('local.refreshList') }}
    </BaseButton>
    <p v-if="error" role="alert">
        {{ error }}
    </p>
    <ElTabs>
        <ElTabPane :label="t('local.fullReplays')" lazy>
            <HistoryVideos v-if="history" :key="history.tournamentId" :order="order" :end-time="history.endTime" @imported="refresh" />
        </ElTabPane>
        <ElTabPane :label="t('local.userCsv')" lazy>
            <HistoryScores kind="users" @imported="refresh" />
        </ElTabPane>
        <ElTabPane :label="t('local.anonymousCsv')" lazy>
            <HistoryScores kind="anonymous" @imported="refresh" />
        </ElTabPane>
    </ElTabs>
    <template v-if="history">
        <p>{{ t('local.parentId') }}{{ history.tournamentId }}</p>
        <code data-cy="history-refresh-command">python manage.py refresh_tournament_scores {{ history.tournamentId }}</code>
        <BaseTable :empty="!history.participants.length" :column-count="5" data-cy="history-participants">
            <template #head>
                <tr><th>{{ t('local.player') }}</th><th>{{ t('local.source') }}</th><th>{{ t('local.replay') }}</th><th>{{ t('local.totalMs') }}</th><th>{{ t('local.action') }}</th></tr>
            </template>
            <tr v-for="participant in history.participants" :key="participant.id">
                <td><PlayerName v-if="participant.user_id !== 0" :user-id="participant.user_id" /><span v-else>{{ participant.arbiter_identifier__identifier }}</span></td>
                <td>{{ participant.manual_scores ? t('local.manual') : t('local.replay') }}</td><td>{{ participant.has_videos ? t('local.yes') : t('local.none') }}</td><td>{{ participant.sum_tsum }}</td>
                <td>
                    <DisqualifyParticipant v-if="history.hostId === store.user.id" :participant="participant" @deleted="refresh" />
                </td>
            </tr>
        </BaseTable>
    </template>
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus-tabs.less';
import { ElTabPane, ElTabs } from 'element-plus';
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import HistoryScores from './HistoryScores.vue';
import HistoryVideos from './HistoryVideos.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import PlayerName from '@/components/PlayerName.vue';
import { fetchGSCHistory } from '@/services/gscHistoryService';
import { store } from '@/store';
import DisqualifyParticipant from '@/views/TournamentView/common/DisqualifyParticipant.vue';

const props = defineProps({ order: { type: Number, required: true } });
const i18nMessages = {
    'zh-cn': { local: {
        historyHint: '仅限已颁奖比赛。录入后不会自动重算，请暂停相关任务，逐届执行下方命令。',
        userCsv: '站内成绩 CSV',
        anonymousCsv: '匿名成绩 CSV',
        parentId: '父表比赛 ID：',
        totalMs: '总成绩 / ms',
        historyTitle: '历史成绩补录',
        refreshList: '刷新管理列表',
        fullReplays: '完整录像',
        source: '成绩来源',
        player: '选手',
        replay: '录像',
        action: '操作',
        manual: '手工',
        none: '无',
        yes: '有',
    } },
    en: { local: {
        historyHint: 'Only awarded tournaments are eligible. Pause related tasks and run the command below for each edition to recalculate results after import.',
        userCsv: 'Registered players\' CSV',
        anonymousCsv: 'Anonymous players\' CSV',
        parentId: 'Parent tournament ID: ',
        totalMs: 'Total / ms',
        historyTitle: 'Import historical results',
        refreshList: 'Refresh administration list',
        fullReplays: 'Complete replays',
        source: 'Score source',
        player: 'Player',
        replay: 'Replay',
        action: 'Action',
        manual: 'Manual',
        none: 'None',
        yes: 'Yes',
    } },
    es: { local: {
        historyHint: 'Solo se admiten torneos ya premiados. Tras la importación, pausa las tareas relacionadas y ejecuta el comando de abajo para recalcular los resultados de cada edición.',
        userCsv: 'CSV de jugadores registrados',
        anonymousCsv: 'CSV de jugadores anónimos',
        parentId: 'ID del torneo principal: ',
        totalMs: 'Total / ms',
        historyTitle: 'Importar resultados históricos',
        refreshList: 'Actualizar la lista de administración',
        fullReplays: 'Repeticiones completas',
        source: 'Origen de la puntuación',
        player: 'Jugador',
        replay: 'Repetición',
        action: 'Acción',
        manual: 'Manual',
        none: 'Ninguno',
        yes: 'Sí',
    } },
};
const { t } = useI18n({ messages: i18nMessages });

const history = ref<Awaited<ReturnType<typeof fetchGSCHistory>>>();
const loading = ref(false);
const error = ref('');
let generation = 0;

async function refresh() {
    const request = ++generation;
    if (props.order <= 0) return;
    const { order } = props;
    loading.value = true;
    error.value = '';
    try {
        const result = await fetchGSCHistory(order);
        if (request === generation) history.value = result;
    } catch (reason) {
        if (request === generation) error.value = String(reason);
    } finally {
        if (request === generation) loading.value = false;
    }
}

watch(() => props.order, () => {
    history.value = undefined;
    loading.value = false;
    void refresh();
}, { immediate: true });
</script>
