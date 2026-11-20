<template>
    <div class="layout-row" style="margin-bottom: 5px;">
        <span class="text-regular">
            <VideoStateIcon v-if="state" :state="state" />
            &nbsp;
            <SoftwareIcon v-if="software" :software="software" />
            &nbsp;
            {{ levelLabel }}
            &nbsp;
            {{ resolvedVideo.mode ? t(`mode.code${resolvedVideo.mode}`) : '—' }}
        </span>
    </div>
    <div v-if="descriptionItems.length > 0" class="description-layout" style="width: 32em; max-width: 100%;">
        <dl class="descriptions descriptions-bordered descriptions-small video-abstract-description-grid">
            <div v-for="entry in descriptionItems" :key="entry.id" class="description-item" :class="`description-width-${entry.width}`">
                <dt>{{ videoColumnLabel(entry.column) }}</dt>
                <dd>
                    <template v-if="isFixedColumn(entry.column)">
                        <VideoListCell v-if="fixedAvailable(entry.column.type)" :video="statistics" :choice="entry.column.type" />
                        <span v-else>—</span>
                    </template>
                    <ExpressionValue v-else :result="expressionResults.get(entry.id) ?? invalidValue" />
                </dd>
            </div>
        </dl>
    </div>
    <span v-if="loading" class="text-secondary">{{ t('local.loading') }}</span>
    <span v-else-if="failed" class="text-secondary">{{ t('local.unavailable') }}</span>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import '@/styles/layout.css';
import type { PropType } from 'vue';
import { computed, ref, shallowRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import SoftwareIcon from './SoftwareIcon.vue';
import VideoStateIcon from './VideoStateIcon.vue';

import { evaluateVideoColumn, isFixedColumn, prepareVideoColumn, videoColumnLabel } from '@/components/VideoList/columns';
import type { FixedColumnType, VideoColumnResult } from '@/components/VideoList/columns';
import { videoDescriptionStore } from '@/components/VideoList/columnStore';
import ExpressionValue from '@/components/VideoList/ExpressionValue.vue';
import VideoListCell from '@/components/VideoList/VideoListCell.vue';
import { fetchVideoInfo, videoDisplayFields } from '@/services/videoInfoService';
import type { VideoDisplayFields } from '@/services/videoInfoService';
import { CustomLevel } from '@/utils/customlevel';
import { isStandardLevel, MS_Softwares, MS_State } from '@/utils/ms_const';
import { VideoAbstract } from '@/utils/videoabstract';
import type { VideoAbstractData } from '@/utils/videoabstract';
import { createVideoExpressionContext } from '@/utils/videoExpression';

const props = defineProps({
    id: { type: Number as PropType<number | null>, default: undefined },
    video: {
        type: Object as PropType<VideoAbstract | Partial<VideoAbstractData> | null>,
        default: undefined,
    },
});

const loadedFields = shallowRef<VideoDisplayFields>();
const loading = ref(false);
const failed = ref(false);
const resolvedVideo = computed(() => (props.video instanceof VideoAbstract
    ? props.video
    : { ...loadedFields.value, ...props.video, bv: props.video?.bv ?? loadedFields.value?.bv ?? NaN }));

watch(() => [props.id ?? props.video?.id, props.video] as const, ([id, video], _, onCleanup) => {
    let active = true;
    onCleanup(() => {
        active = false;
    });
    loadedFields.value = undefined;
    loading.value = false;
    failed.value = false;
    if (id == null || id <= 0 || video instanceof VideoAbstract) return;
    loading.value = true;
    void fetchVideoInfo(id).then((row) => {
        if (active) loadedFields.value = videoDisplayFields(row);
    }).catch(() => {
        if (active) failed.value = true;
    }).finally(() => {
        if (active) loading.value = false;
    });
}, { immediate: true });

const state = computed(() => Object.values(MS_State).find((value) => value === resolvedVideo.value.state));
const software = computed(() => MS_Softwares.find((value) => value === resolvedVideo.value.software));
const statistics = computed(() => (resolvedVideo.value instanceof VideoAbstract
    ? resolvedVideo.value
    : new VideoAbstract({
        ...resolvedVideo.value,
        level: resolvedVideo.value.level ?? '',
        mode: resolvedVideo.value.mode ?? '00',
        software: resolvedVideo.value.software ?? '',
        timems: resolvedVideo.value.timems ?? NaN,
        bv: resolvedVideo.value.bv,
    })));

const { columns: descriptionColumns } = videoDescriptionStore;
const descriptionItems = computed(() => descriptionColumns.value.map((column) => ({ ...prepareVideoColumn(column), width: column.width })));
const expressionResults = computed(() => {
    const source = resolvedVideo.value;
    const context = createVideoExpressionContext(statistics.value, source instanceof VideoAbstract ? undefined : source);
    return new Map(descriptionItems.value.filter((entry) => !isFixedColumn(entry.column)).map((entry) => [entry.id, evaluateVideoColumn(entry, context, true)]));
});
const invalidValue: VideoColumnResult = { text: 'NaN', sortValue: NaN, error: '' };
function fixedAvailable(type: FixedColumnType): boolean {
    const source = resolvedVideo.value;
    const value = type === 'player' ? source.player_id ?? ('player' in source ? source.player : undefined) : source[type];
    return value !== null && value !== undefined && value !== '';
}

const levelLabel = computed(() => {
    const { level } = statistics.value;
    if (state.value === MS_State.Local && !isStandardLevel(level)) return '—';
    if (level instanceof CustomLevel) {
        return t('level.c', {
            column: level.column,
            mine: level.mine,
            row: level.row,
        });
    }
    return isStandardLevel(level) ? t(`level.${level}`) : '—';
});

const i18nMessages = {
    'zh-cn': { local: {
        loading: '正在获取录像信息…',
        unavailable: '录像信息暂不可用',
    } },
    en: { local: {
        loading: 'Loading video information…',
        unavailable: 'Video information is unavailable',
    } },
    es: { local: {
        loading: 'Cargando información del video…',
        unavailable: 'La información del video no está disponible',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-abstract-description-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
}
.description-width-2 {
    grid-column: span 2;
}
.description-width-3 {
    grid-column: span 3;
}
.description-item dd {
    white-space: pre-wrap;
}
@container descriptions (width < 20rem) {
    .video-abstract-description-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .description-width-3 {
        grid-column: span 2;
    }
}
@container descriptions (width < 12rem) {
    .video-abstract-description-grid {
        grid-template-columns: minmax(0, 1fr);
    }
    .description-width-2,
    .description-width-3 {
        grid-column: span 1;
    }
}
</style>
