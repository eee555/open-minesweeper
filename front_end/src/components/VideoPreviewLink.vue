<template>
    <Tippy v-if="id != null && id > 0" ref="tooltip" tag="a" :href="`#/video/${id}`" class="link video-preview-link" :duration="0" sticky :on-show="showSummary" :on-hidden="hideSummary" @click="handleClick" @auxclick.stop>
        <SoftwareIcon v-if="showSoftware && resolvedSoftware" :software="resolvedSoftware" class="video-preview-software" />
        <slot />
        <template #content>
            <div v-if="summaryVisible" class="card card-small">
                <VideoAbstractDisplay :id="id" :video="suppliedVideo" />
            </div>
        </template>
    </Tippy>
    <span v-else>--</span>
</template>

<script setup lang="ts">
import '@/styles/link.css';
import '@/styles/cards.css';
import type { PropType } from 'vue';
import { computed, ref, shallowRef, useTemplateRef, watch } from 'vue';
import { Tippy } from 'vue-tippy';
import type { TippyComponent } from 'vue-tippy';

import SoftwareIcon from '@/components/widgets/SoftwareIcon.vue';
import VideoAbstractDisplay from '@/components/widgets/VideoAbstractDisplay.vue';
import { fetchVideoInfo } from '@/services/videoInfoService';
import { preview } from '@/utils/common/PlayerDialog';
import type { MS_Software } from '@/utils/ms_const';
import type { VideoAbstract } from '@/utils/videoabstract';

const props = defineProps({
    id: { type: Number as PropType<number | null>, default: 0 },
    software: { type: String as PropType<MS_Software>, default: undefined },
    video: { type: Object as PropType<VideoAbstract>, default: undefined },
    showSoftware: { type: Boolean, default: true },
    showTooltip: { type: Boolean, default: true },
});

const loadedSoftware = shallowRef<MS_Software>();
const tooltip = useTemplateRef<TippyComponent>('tooltip');
const summaryVisible = ref(false);
const suppliedVideo = computed(() => (props.video?.id === props.id ? props.video : undefined));
const suppliedSoftware = computed(() => props.software ?? suppliedVideo.value?.software);
const resolvedSoftware = computed(() => suppliedSoftware.value ?? loadedSoftware.value);

watch(() => [props.id, suppliedSoftware.value, props.showSoftware] as const, ([id, software, showSoftware], _, onCleanup) => {
    let active = true;
    onCleanup(() => {
        active = false;
    });
    tooltip.value?.hide();
    loadedSoftware.value = undefined;
    summaryVisible.value = false;
    if (id == null || id <= 0 || software !== undefined || !showSoftware) return;
    void fetchVideoInfo(id).then((row) => {
        if (active) loadedSoftware.value = row.software;
    }).catch(() => {
        // The link remains usable; the summary or player reports a failed retry when requested.
    });
}, { immediate: true });

function showSummary() {
    if (!props.showTooltip) return false;
    summaryVisible.value = true;
}

function hideSummary() {
    summaryVisible.value = false;
}

defineSlots<{
    default: () => unknown;
}>();

function handleClick(event: MouseEvent) {
    event.stopPropagation();
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    void preview(props.id, resolvedSoftware.value);
}
</script>

<style scoped>
.video-preview-link {
    color: inherit;
    font: inherit;
    cursor: pointer;
}

.video-preview-software {
    vertical-align: text-bottom;
    margin-inline-end: 0.25em;
}
</style>
