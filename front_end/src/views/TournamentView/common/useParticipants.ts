import { computed, onScopeDispose, reactive, ref, shallowRef, watch } from 'vue';
import type { ComputedRef, Ref, ShallowRef } from 'vue';

import { httpErrorNotification } from '@/components/Notifications';
import { fetchParticipantList } from '@/services/tournamentService';
import { store } from '@/store';
import { LoginStatus } from '@/utils/common/structInterface';
import { globalNow } from '@/utils/datetime';
import { TournamentState, TournamentSubclass } from '@/utils/ms_const';
import type { Tournament, TournamentParticipant } from '@/utils/tournaments';

interface ParticipantState<T> {
    participants: ShallowRef<T[]>;
    index: ComputedRef<number>;
    participant: ComputedRef<T | null>;
    loading: Ref<boolean>;
    state: ComputedRef<TournamentState>;
    refresh: () => Promise<void>;
    registered: (item: T) => void;
    deleted: (id: number) => void;
}

export function useParticipants<T extends TournamentParticipant>(tournament: () => Tournament, create: (participant: TournamentParticipant) => T, fetchResults: (id: number) => Promise<T[]>): ParticipantState<T> {
    const participants = shallowRef<T[]>([]);
    const loading = ref(false);
    const state = computed(() => tournament().getDisplayState(globalNow.value));
    const index = computed(() => (store.login_status === LoginStatus.IsLogin ? participants.value.findIndex((item) => item.user_id === store.user.id) : -1));
    const participant = computed(() => participants.value[index.value] ?? null);
    let request = 0;

    async function refresh() {
        const currentRequest = ++request;
        const { id } = tournament();
        const awarded = state.value === TournamentState.Awarded;
        const preparingGSC = state.value === TournamentState.Preparing && tournament().subclass === TournamentSubclass.GSC;
        if (!awarded && !preparingGSC && state.value !== TournamentState.Ongoing && state.value !== TournamentState.Finished) {
            participants.value = [];
            loading.value = false;
            return;
        }
        loading.value = true;
        try {
            const incoming = awarded ? await fetchResults(id) : (await fetchParticipantList(id)).map(create);
            if (currentRequest !== request) return;
            const previous = new Map(participants.value.map((item) => [item.id, item]));
            participants.value = incoming.map((item) => {
                const existing = awarded ? undefined : previous.get(item.id);
                // eslint-disable-next-line @typescript-eslint/no-unsafe-class-instance-assignment -- reactive() 保留原型链，代理仍是 T 的实例
                if (!existing) return reactive(item) as T;
                const { videos } = existing;
                Object.assign(existing, item);
                if (videos !== undefined) existing.videos = videos;
                return existing;
            });
        } catch (error) {
            if (currentRequest === request) httpErrorNotification(error);
        } finally {
            if (currentRequest === request) loading.value = false;
        }
    }

    function registered(item: T) {
        request += 1;
        loading.value = false;
        // eslint-disable-next-line @typescript-eslint/no-unsafe-class-instance-assignment -- reactive() 保留原型链，代理仍是 T 的实例
        participants.value = [...participants.value.filter((entry) => entry.id !== item.id), reactive(item) as T];
    }
    function deleted(id: number) {
        request += 1;
        loading.value = false;
        participants.value = participants.value.filter((item) => item.id !== id);
    }
    watch(() => tournament().id, () => {
        participants.value = [];
    });
    watch([() => tournament().id, state, () => store.login_status, () => store.user.id], refresh, { immediate: true });
    onScopeDispose(() => {
        request += 1;
    });
    return { participants, index, participant, loading, state, refresh, registered, deleted };
}
