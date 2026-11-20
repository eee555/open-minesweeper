<template>
    <PublicTournament :tournament="tournament" :participants="participants" :index="index" :loading="loading" :refresh-participants="refresh" :auto-uploader-enabled="store.canSubmitReplays" :auto-uploader-filter="matchesFilter">
        <template #description>
            <p class="text">
                {{ t('local.description') }}
            </p>
        </template>
        <template #participationGuide>
            <TokenGuide :token="participant?.token ?? ''" :participant="participant" :registration-open="state === TournamentState.Ongoing" :tournament-id="tournament.id" :register="createWeeklyEffParticipant" @registered="registered(new WeeklyEffParticipant($event))" />
        </template>
        <template #autoUploaderFilter>
            <select v-model="filterLevel" class="base-select base-select--small" :aria-label="t('filter')">
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
            <AllSummary v-if="state === TournamentState.Awarded" :data="data" :can-disqualify="canDisqualify" @row-click="onParticipantSelect" @deleted="deleted" />
            <Registered v-else :participants="data" :loading="loading" :can-manage="canManage" @deleted="deleted" />
        </template>
        <template #personalSummary="{ videos }">
            <PersonalSummary :videos="videos" />
        </template>
    </PublicTournament>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import PublicTournament from '../common/PublicTournament.vue';
import { useParticipants } from '../common/useParticipants';
import type { AutoUploadVideo } from '../common/utils';
import Registered from '../weekly/Registered.vue';
import TokenGuide from '../weekly/TokenGuide.vue';

import AllSummary from './AllSummary.vue';
import PersonalSummary from './PersonalSummary.vue';

import { createWeeklyEffParticipant, fetchWeeklyEffResults } from '@/services/tournamentService';
import { store } from '@/store';
import { LoginStatus } from '@/utils/common/structInterface';
import { TournamentState } from '@/utils/ms_const';
import { Tournament } from '@/utils/tournaments';
import { isWeeklyEffSupportedVideo, WeeklyEffParticipant, weeklyEffVideoScore } from '@/utils/weeklyEff';

const props = defineProps({ tournament: { type: Tournament, required: true } });
const { participants, index, participant, loading, state, refresh, registered, deleted } = useParticipants(() => props.tournament, (item) => new WeeklyEffParticipant(item), fetchWeeklyEffResults);
const canManage = computed(() => state.value === TournamentState.Ongoing && store.login_status === LoginStatus.IsLogin && (store.user.is_staff || store.user.id === props.tournament.hostId));
const canDisqualify = computed(() => store.login_status === LoginStatus.IsLogin && store.user.id === props.tournament.hostId);
const filterLevel = ref('supported');

function matchesFilter(video: AutoUploadVideo): boolean {
    const player = participant.value;
    if (player === null || player.token === '' || video.stat.software === 'a' || !video.tokens.includes(player.token)) return false;
    if (filterLevel.value === 'tournament') return true;
    if (!isWeeklyEffSupportedVideo(video.stat)) return false;
    if (filterLevel.value === 'supported') return true;
    const scores = video.stat.level === 'i' ? player.it : player.et;
    return weeklyEffVideoScore(video.stat) < scores[scores.length - 1][1];
}

const i18nMessages = {
    'zh-cn': { local: {
        description: '标准模式，取 time / IOE² 最低的 2 局高级和 5 局中级之和。中级须低于 60，高级须低于 240；缺项按该上限计分。',
        tournament: '所有比赛录像',
        supported: '有效的比赛录像',
        scoreRefreshing: '刷新成绩的比赛录像',
    } },
    en: { local: {
        description: 'Standard mode: sum the lowest time / IOE² from 2 Expert and 5 Intermediate games. Intermediate must be below 60, Expert below 240; missing games count as these limits.',
        tournament: 'All tournament videos',
        supported: 'Supported tournament videos',
        scoreRefreshing: 'Score-improving videos',
    } },
    es: { local: {
        description: 'Modo estándar: suma los valores más bajos de tiempo / IOE² de 2 juegos expertos y 5 juegos intermedios. Los juegos intermedios deben estar por debajo de 60 y los expertos por debajo de 240; los juegos faltantes se cuentan como estos límites.',
        tournament: 'Todos los videos del torneo',
        supported: 'Videos del torneo compatibles',
        scoreRefreshing: 'Videos que mejoran los puntajes',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
