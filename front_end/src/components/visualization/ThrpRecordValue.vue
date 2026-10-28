<template>
    <details v-if="stat === 'e_nf' && record?.e_nf && record.e_nf.video_ids.length > 1" class="thrp-record-value" @toggle="expanded = ($event.target as HTMLDetailsElement).open">
        <summary>{{ text }}</summary>
        <template v-if="expanded">
            <div v-for="id in record.e_nf.video_ids" :key="id">
                <VideoPreviewLink :id="id">
                    1.000 (#{{ id }})
                </VideoPreviewLink>
            </div>
        </template>
    </details>
    <VideoPreviewLink v-else-if="videoId" :id="videoId">
        {{ text }}
    </VideoPreviewLink>
    <template v-else>
        {{ text }}
    </template>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { PropType } from 'vue';

import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import { formatThrpValue, thrpVideoId } from '@/services/thrpRankingService';
import type { ThrpRecord, ThrpStat } from '@/services/thrpRankingService';

const props = defineProps({
    record: { type: Object as PropType<ThrpRecord>, default: undefined },
    stat: { type: String as PropType<ThrpStat>, required: true },
    rank: { type: Number as PropType<number | null>, default: undefined },
});
const expanded = ref(false);
const videoId = computed(() => (props.record ? thrpVideoId(props.record, props.stat) : undefined));
const text = computed(() => `${formatThrpValue(props.record, props.stat)}${props.rank === undefined ? '' : `(${props.rank ?? '--'})`}`);
</script>

<style scoped>
.thrp-record-value summary {
    cursor: pointer;
}
</style>
