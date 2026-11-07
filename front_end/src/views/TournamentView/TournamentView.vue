<template>
    <ElTabs v-if="tournamentId === undefined" v-model="currentListTab" @tab-change="loadTournamentList">
        <ElTabPane v-for="tab in listTabs" :key="tab.name" :label="t(tab.label)" :name="tab.name" lazy>
            <TournamentList :tournament-list="tournamentLists[tab.name]" />
        </ElTabPane>
    </ElTabs>
    <GSCApp v-else-if="tournament?.subclass === TournamentSubclass.GSC" :tournament="tournament" />
    <WeeklyApp v-else-if="tournament?.subclass === TournamentSubclass.Weekly" :tournament="tournament" />
    <TournamentDetail v-else-if="tournament" :tournament="tournament" />
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus-tabs.less';
import type { TabPaneName } from 'element-plus';
import { ElTabPane, ElTabs } from 'element-plus';
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import GSCApp from './gsc/App.vue';
import TournamentDetail from './TournamentDetail.vue';
import TournamentList from './TournamentList.vue';
import WeeklyApp from './weekly/App.vue';

import { httpErrorNotification } from '@/components/Notifications';
import { fetchTournament, fetchTournamentList } from '@/services/tournamentService';
import type { TournamentListCategory } from '@/services/tournamentService';
import { TournamentSubclass } from '@/utils/ms_const';
import { Tournament } from '@/utils/tournaments';

const { t } = useI18n();

const listTabs: { name: TournamentListCategory; label: string }[] = [
    { name: 'normal', label: 'tournament.listTabs.normal' },
    { name: 'awarded', label: 'tournament.listTabs.awarded' },
    { name: 'other', label: 'tournament.listTabs.other' },
    { name: 'all', label: 'tournament.listTabs.all' },
];
const currentListTab = ref<TournamentListCategory>('normal');
const tournamentLists = ref<Record<TournamentListCategory, Tournament[]>>({
    normal: [],
    awarded: [],
    other: [],
    all: [],
});
const loadedListTabs = ref<Set<TournamentListCategory>>(new Set());

function isTournamentListCategory(value: TabPaneName): value is TournamentListCategory {
    return typeof value === 'string' && listTabs.some((tab) => tab.name === value);
}

function loadTournamentList(tab: TabPaneName = currentListTab.value) {
    if (!isTournamentListCategory(tab)) return;
    if (loadedListTabs.value.has(tab)) return;

    fetchTournamentList(tab).then((data) => {
        tournamentLists.value[tab] = data.map((tournament) => new Tournament(tournament));
        loadedListTabs.value.add(tab);
    }).catch(httpErrorNotification);
}

const route = useRoute();
const tournament = ref<Tournament>();

const tournamentId = computed(() => {
    const { id } = route.params;
    if (typeof id !== 'string') return undefined;
    return id;
});

watch(tournamentId, async (newId) => {
    tournament.value = undefined;
    if (newId === undefined) {
        loadTournamentList();
        return;
    }

    await fetchTournament(newId).then((data) => {
        tournament.value = new Tournament(data);
    }).catch(httpErrorNotification);
}, { immediate: true });
</script>
