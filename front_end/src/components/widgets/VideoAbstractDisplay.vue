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
    <div class="description-layout" style="width: 32em; max-width: 100%;">
        <dl class="descriptions descriptions-bordered descriptions-small">
            <div v-if="uploadTime && state !== MS_State.Local" class="description-item description-wide">
                <dt>{{ t('prop.upload_time') }}</dt>
                <dd>
                    {{ toISODateTimeString(uploadTime) }}
                </dd>
            </div>

            <div v-if="endTime" class="description-item description-wide">
                <dt>{{ t('prop.end_time') }}</dt>
                <dd>
                    {{ toISODateTimeString(endTime) }}
                </dd>
            </div>

            <div class="description-item">
                <dt>{{ t('prop.time') }}</dt>
                <dd>
                    {{ displayStat('time') }}
                </dd>
            </div>
            <div class="description-item">
                <dt>{{ t('prop.bv') }}</dt>
                <dd>
                    {{ displayStat('bv') }}
                </dd>
            </div>
            <div class="description-item">
                <dt>{{ t('prop.stnb') }}</dt>
                <dd>
                    {{ displayStat('stnb') }}
                </dd>
            </div>

            <div class="description-item">
                <dt>{{ t('prop.bvs') }}</dt>
                <dd>
                    {{ displayStat('bvs') }}
                </dd>
            </div>
            <div class="description-item">
                <dt>{{ t('prop.cl_s') }}</dt>
                <dd>
                    {{ displayStat('cls') }}
                </dd>
            </div>
            <div class="description-item">
                <dt>{{ t('prop.ce_s') }}</dt>
                <dd>
                    {{ displayStat('ces') }}
                </dd>
            </div>

            <div class="description-item">
                <dt>{{ t('prop.ioe') }}</dt>
                <dd>
                    {{ displayStat('ioe') }}
                </dd>
            </div>
            <div class="description-item">
                <dt>{{ t('prop.thrp') }}</dt>
                <dd>
                    {{ displayStat('thrp') }}
                </dd>
            </div>
            <div class="description-item">
                <dt>{{ t('prop.corr') }}</dt>
                <dd>
                    {{ displayStat('corr') }}
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

import { fetchVideoInfo, videoDisplayFields } from '@/services/videoInfoService';
import type { VideoDisplayFields } from '@/services/videoInfoService';
import { CustomLevel } from '@/utils/customlevel';
import { toDate, toISODateTimeString } from '@/utils/datetime';
import { isStandardLevel, MS_Softwares, MS_State } from '@/utils/ms_const';
import { VideoAbstract } from '@/utils/videoabstract';
import type { getStat_stat, VideoAbstractData } from '@/utils/videoabstract';

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

function validDate(value: string | Date | null | undefined) {
    const date = toDate(value);
    return date !== undefined && Number.isFinite(date.getTime()) ? date : undefined;
}

const uploadTime = computed(() => {
    const video = resolvedVideo.value;
    return validDate(video instanceof VideoAbstract ? video.upload_time : video.upload_time ?? video.time);
});
const endTime = computed(() => validDate(resolvedVideo.value.end_time));

function displayStat(stat: getStat_stat): string {
    return Number.isFinite(statistics.value[stat]) ? statistics.value.displayStat(stat) : '—';
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
};
const { t } = useI18n({ messages: i18nMessages });
</script>
