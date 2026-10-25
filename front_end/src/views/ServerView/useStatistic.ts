import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue';
import type { Ref, ShallowRef } from 'vue';

import useCurrentInstance from '@/utils/common/useCurrentInstance';

interface StatisticState<T> {
    data: ShallowRef<T | null>;
    loading: Ref<boolean>;
    failed: Ref<boolean>;
    refresh: () => Promise<void>;
}

export function useStatistic<T>(path: string): StatisticState<T> {
    const { proxy } = useCurrentInstance();
    const data = shallowRef<T | null>(null);
    const loading = ref(false);
    const failed = ref(false);
    let controller: AbortController | null = null;

    async function refresh() {
        if (loading.value) return;
        controller = new AbortController();
        const { signal } = controller;
        loading.value = true;
        failed.value = false;
        try {
            const response = await proxy.$axios.get<T>(path, { signal });
            data.value = response.data;
        } catch {
            if (!signal.aborted) failed.value = true;
        } finally {
            loading.value = false;
        }
    }

    onMounted(refresh);
    onBeforeUnmount(() => controller?.abort());
    return { data, loading, failed, refresh };
}
