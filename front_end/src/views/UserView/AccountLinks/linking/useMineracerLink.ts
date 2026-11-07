import { onBeforeUnmount, ref, watch } from 'vue';
import type { Ref } from 'vue';

import { httpErrorNotification } from '@/components/Notifications';
import { fetchMineracerAccountLinkSession, getMineracerAccountLinkHttpErrorCategory, startMineracerAccountLinkSession } from '@/services/mineracerService';
import type { MineracerAccountLinkSession } from '@/utils/accountlinks';

export interface MineracerLinkState {
    session: Ref<MineracerAccountLinkSession | undefined>;
    startLoading: Ref<boolean>;
    statusLoading: Ref<boolean>;
    httpErrorMessageKey: Ref<string>;
    startLink: () => Promise<void>;
    pollSession: () => Promise<void>;
}

export function useMineracerLink(enabled: Ref<boolean>, refresh: () => Promise<void>): MineracerLinkState {
    const session = ref<MineracerAccountLinkSession>();
    const startLoading = ref(false);
    const statusLoading = ref(false);
    const httpErrorMessageKey = ref('');
    let active = true;
    let timer: number | undefined;
    let refreshedSession = '';
    const clearTimer = () => {
        window.clearTimeout(timer); timer = undefined;
    };
    function schedule(delay?: number) {
        clearTimer();
        if (!active || !enabled.value || session.value?.status !== 'pending') return;
        const next = session.value.next_poll_at?.getTime() ?? Date.now() + 2500;
        const due = Math.min(next, session.value.expires_at.getTime());
        timer = window.setTimeout(() => {
            void pollSession();
        }, delay ?? Math.max(500, due - Date.now()));
    }
    function apply(next: MineracerAccountLinkSession) {
        if (!active) return;
        session.value = next;
        if (next.status === 'confirmed' && refreshedSession !== next.session_id) {
            refreshedSession = next.session_id;
            void refresh();
        }
        schedule();
    }
    function report(error: unknown) {
        if (!active) return;
        const category = getMineracerAccountLinkHttpErrorCategory(error);
        if (category !== undefined) httpErrorMessageKey.value = category;
        else if (enabled.value) httpErrorNotification(error);
    }
    async function startLink() {
        if (!active || !enabled.value || startLoading.value || session.value?.status === 'pending') return;
        clearTimer();
        startLoading.value = true;
        httpErrorMessageKey.value = '';
        try {
            apply(await startMineracerAccountLinkSession());
        } catch (error) {
            report(error);
        } finally {
            if (active) startLoading.value = false;
        }
    }
    async function pollSession() {
        if (!active || !enabled.value || statusLoading.value || startLoading.value || session.value?.status !== 'pending') return;
        clearTimer();
        statusLoading.value = true;
        httpErrorMessageKey.value = '';
        try {
            apply(await fetchMineracerAccountLinkSession(session.value.session_id));
        } catch (error) {
            report(error); schedule(2500);
        } finally {
            if (active) statusLoading.value = false;
        }
    }
    watch(enabled, (value) => {
        if (value) void pollSession(); else clearTimer();
    });
    onBeforeUnmount(() => {
        active = false; clearTimer();
    });
    return { session, startLoading, statusLoading, httpErrorMessageKey, startLink, pollSession };
}
