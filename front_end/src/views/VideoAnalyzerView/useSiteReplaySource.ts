import { isAxiosError, isCancel } from 'axios';
import { ref, shallowRef, toValue, watch } from 'vue';
import type { MaybeRefOrGetter, Ref, ShallowRef } from 'vue';

import type { ReplaySource } from '@/components/VideoAnalyzer/replayParser';
import { fetchReplayFile } from '@/services/replayFileService';
import { fetchVideoInfo } from '@/services/videoInfoService';
import { getSoftwareExtension } from '@/utils/strings';

export interface SiteReplaySourceState {
    source: ShallowRef<ReplaySource | null>;
    loading: Ref<boolean>;
    errorMessage: Ref<string>;
}

export function useSiteReplaySource(id: MaybeRefOrGetter<string>): SiteReplaySourceState {
    const source = shallowRef<ReplaySource | null>(null);
    const loading = ref(false);
    const errorMessage = ref('');
    watch(() => toValue(id), async (videoId, _previous, onCleanup) => {
        const controller = new AbortController();
        onCleanup(() => {
            controller.abort();
            source.value = null;
        });
        loading.value = true;
        errorMessage.value = '';
        try {
            const video = await fetchVideoInfo(Number(videoId));
            if (controller.signal.aborted) return;
            const { software } = video;
            const filename = videoId + getSoftwareExtension(software);
            const response = await fetchReplayFile('/api/video/preview', { params: { id: filename }, signal: controller.signal, filename });
            if (controller.signal.aborted) return;
            source.value = { data: response.data, filename: response.filename, software };
        } catch (error) {
            if (controller.signal.aborted || isCancel(error)) return;
            errorMessage.value = isAxiosError(error) && error.response !== undefined
                ? `${error.response.status} ${error.response.statusText}`.trim()
                : error instanceof Error ? error.message : String(error);
        } finally {
            if (!controller.signal.aborted) loading.value = false;
        }
    }, { immediate: true });
    return { source, loading, errorMessage };
}
