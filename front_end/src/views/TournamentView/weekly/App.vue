<template>
    <PublicTournament :tournament="tournament" :participants="participants" :index="index" :loading="loading" :refresh-participants="refresh" :auto-uploader-enabled="store.canSubmitReplays" :auto-uploader-filter="matchesFilter">
        <template #description>
            <Description />
        </template>
        <template #participationGuide>
            <TokenGuide :token="participant?.token ?? ''" :participant="participant" :registration-open="state === TournamentState.Ongoing" :tournament-id="tournament.id" @registered="registered" />
        </template>
        <template #autoUploaderFilter>
            <select v-model="filterLevel" class="base-select base-select--small" style="width: 250px" :aria-label="t('filter')">
                <option value="tournament">
                    {{ t('local.tournament') }}
                </option>
                <option value="supported">
                    {{ t('local.supported') }}
                </option>
                <option value="scoreRefreshing">
                    {{ t('local.scoreRefreshing') }}
                </option>
            </select>
        </template>
        <template #allSummary="{ data, onParticipantSelect }">
            <AllSummary v-if="state === TournamentState.Awarded" :data="data" @row-click="onParticipantSelect" />
            <Registered v-else :participants="data" :loading="loading" :can-manage="canManage" @deleted="deleted" />
        </template>
        <template #personalSummary="{ videos }">
            <PersonalSummary :tournament-format="format" :videos="videos" />
        </template>
    </PublicTournament>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import PublicTournament from '../common/PublicTournament.vue';
import { useParticipants } from '../common/useParticipants';
import type { AutoUploadVideo } from '../common/utils';

import AllSummary from './AllSummary.vue';
import Description from './Description.vue';
import PersonalSummary from './PersonalSummary.vue';
import Registered from './Registered.vue';
import TokenGuide from './TokenGuide.vue';

import { fetchWeeklyResults } from '@/services/tournamentService';
import { store } from '@/store';
import { LoginStatus } from '@/utils/common/structInterface';
import { MS_Mode, TournamentState } from '@/utils/ms_const';
import { Tournament } from '@/utils/tournaments';
import { WeeklyParticipant, WeeklyTournamentFormat } from '@/utils/weekly';

const props = defineProps({ tournament: { type: Tournament, required: true } });
const { participants, index, participant, loading, state, refresh, registered, deleted } = useParticipants(() => props.tournament, (item) => new WeeklyParticipant(item), fetchWeeklyResults);
const format = computed(() => props.tournament.weeklyData?.tournament_format ?? WeeklyTournamentFormat.Classic);
const canManage = computed(() => store.login_status === LoginStatus.IsLogin && (store.user.is_staff || store.user.id === props.tournament.hostId));

const filterLevel = ref('supported');

function matchesFilter(video: AutoUploadVideo): boolean {
    if (participant.value === null) return false;
    if (video.stat.software === 'a' || !participant.value.token) return false;
    if (!video.tokens.includes(participant.value.token)) return false;
    if (filterLevel.value === 'tournament') return true;
    if (format.value !== WeeklyTournamentFormat.Classic || video.stat.mode !== MS_Mode.Standard) return false;
    if (video.stat.level !== 'i' && video.stat.level !== 'e') return false;
    if (filterLevel.value === 'supported') return true;
    return video.stat.timems < (video.stat.level === 'i' ? participant.value.classic_it[4][1] : participant.value.classic_et[1][1]);
}

const i18nMessages = {
    'zh-cn': { local: {
        tournament: '所有比赛录像',
        supported: '有效的比赛录像',
        scoreRefreshing: '刷新成绩的比赛录像',
    } },
    en: { local: {
        tournament: 'All tournament videos',
        supported: 'Supported tournament videos',
        scoreRefreshing: 'Score-improving videos',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
