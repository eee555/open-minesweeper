import { onBeforeUnmount, ref, watch } from 'vue';
import type { Ref } from 'vue';

import { httpErrorNotification } from '@/components/Notifications';
import { fetchClassicAccountLink, getClassicAccountLinkHttpErrorCategory, startClassicAccountLink } from '@/services/classicService';
import { ClassicAccountLink } from '@/utils/accountlinks';

export interface ClassicLinkState {
    link: Ref<ClassicAccountLink>;
    uid: Ref<string>;
    startLoading: Ref<boolean>;
    statusLoading: Ref<boolean>;
    httpErrorMessageKey: Ref<string>;
    refreshStatus: () => Promise<void>;
    submit: () => Promise<void>;
}

export function useClassicLink(enabled: Ref<boolean>, refresh: () => Promise<void>): ClassicLinkState {
    const link = ref(new ClassicAccountLink());
    const uid = ref('');
    const startLoading = ref(false);
    const statusLoading = ref(false);
    const httpErrorMessageKey = ref('');
    let active = true;
    let timer: number | undefined;
    let refreshedRequest: number | undefined;
    const clearTimer = () => {
        window.clearTimeout(timer); timer = undefined;
    };
    function apply(next: ClassicAccountLink) {
        if (!active) return;
        link.value = next;
        clearTimer();
        if (enabled.value && next.status === 'pending') timer = window.setTimeout(() => {
            void refreshStatus();
        }, 5000);
        const request = next.request_id ?? next.uid ?? 0;
        if (next.status === 'allow' && refreshedRequest !== request) {
            refreshedRequest = request;
            void refresh();
        }
    }
    async function refreshStatus() {
        if (!active || !enabled.value || startLoading.value || statusLoading.value) return;
        clearTimer();
        httpErrorMessageKey.value = '';
        statusLoading.value = true;
        try {
            apply(await fetchClassicAccountLink());
        } catch (error) {
            if (active && enabled.value) {
                httpErrorNotification(error);
                if (link.value.status === 'pending') timer = window.setTimeout(() => {
                    void refreshStatus();
                }, 5000);
            }
        } finally {
            if (active) statusLoading.value = false;
        }
    }
    async function submit() {
        if (!active || !enabled.value || startLoading.value || !(/^[1-9]\d{7}$/).test(uid.value)) return;
        clearTimer();
        startLoading.value = true;
        httpErrorMessageKey.value = '';
        try {
            apply(await startClassicAccountLink(uid.value));
        } catch (error) {
            if (!active) return;
            const category = getClassicAccountLinkHttpErrorCategory(error);
            if (category !== undefined) httpErrorMessageKey.value = category;
            else if (enabled.value) httpErrorNotification(error);
        } finally {
            if (active) startLoading.value = false;
        }
    }
    watch(enabled, (value) => {
        if (value) void refreshStatus(); else clearTimer();
    }, { immediate: true });
    onBeforeUnmount(() => {
        active = false; clearTimer();
    });
    return { link, uid, startLoading, statusLoading, httpErrorMessageKey, refreshStatus, submit };
}
