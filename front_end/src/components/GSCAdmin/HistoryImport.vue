<template>
    <h3>历史成绩补录</h3>
    <p>仅限已颁奖比赛。录入后不会自动重算，请暂停相关任务，逐届执行下方命令。</p>
    <BaseButton :loading="loading" :disabled="order <= 0" data-cy="history-refresh" @click="refresh">
        刷新管理列表
    </BaseButton>
    <p v-if="error" role="alert">
        {{ error }}
    </p>
    <ElTabs>
        <ElTabPane label="完整录像" lazy>
            <HistoryVideos v-if="history" :key="history.tournamentId" :order="order" :end-time="history.endTime" @imported="refresh" />
        </ElTabPane>
        <ElTabPane label="站内成绩 CSV" lazy>
            <HistoryScores kind="users" @imported="refresh" />
        </ElTabPane>
        <ElTabPane label="匿名成绩 CSV" lazy>
            <HistoryScores kind="anonymous" @imported="refresh" />
        </ElTabPane>
    </ElTabs>
    <template v-if="history">
        <p>父表比赛 ID：{{ history.tournamentId }}</p>
        <code data-cy="history-refresh-command">python manage.py refresh_tournament_scores {{ history.tournamentId }}</code>
        <BaseTable :empty="!history.participants.length" :column-count="5" data-cy="history-participants">
            <template #head>
                <tr><th>选手</th><th>成绩来源</th><th>录像</th><th>总成绩 / ms</th><th>操作</th></tr>
            </template>
            <tr v-for="participant in history.participants" :key="participant.id">
                <td><PlayerName v-if="participant.user_id !== 0" :user-id="participant.user_id" /><span v-else>{{ participant.arbiter_identifier__identifier }}</span></td>
                <td>{{ participant.manual_scores ? '手工' : '录像' }}</td><td>{{ participant.has_videos ? '有' : '无' }}</td><td>{{ participant.sum_tsum }}</td>
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

import HistoryScores from './HistoryScores.vue';
import HistoryVideos from './HistoryVideos.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import PlayerName from '@/components/PlayerName.vue';
import { fetchGSCHistory } from '@/services/gscHistoryService';
import { store } from '@/store';
import DisqualifyParticipant from '@/views/TournamentView/common/DisqualifyParticipant.vue';

const props = defineProps({ order: { type: Number, required: true } });
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
