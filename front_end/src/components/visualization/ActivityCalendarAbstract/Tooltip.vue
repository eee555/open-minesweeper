<template>
    <div class="card card-small">
        <span v-if="videos.length == 0" class="text-regular">
            {{ t('local.noVideoOnDate', [toISODateString(date)]) }}
        </span>
        <template v-else>
            <span class="text-regular">
                {{ t('local.uploadedNVideosOnDate', [toISODateString(date), videos.length]) }}
            </span>
            <br>
            <span v-for="i in count.b" :key="`b-${i}`" class="dot" :style="{ backgroundColor: colorTheme.level.b }" />
            <span v-for="i in count.i" :key="`i-${i}`" class="dot" :style="{ backgroundColor: colorTheme.level.i }" />
            <span v-for="i in count.e" :key="`e-${i}`" class="dot" :style="{ backgroundColor: colorTheme.level.e }" />
            <span v-for="i in count.c" :key="`c-${i}`" class="dot" :style="{ backgroundColor: colorTheme.level.c }" />
        </template>
    </div>
</template>

<script setup lang="ts">
import '@/styles/cards.css';

import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { colorTheme } from '@/store';
import { toISODateString } from '@/utils/datetime';
import { isStandardLevel } from '@/utils/ms_const';
import type { VideoAbstract } from '@/utils/videoabstract';

const props = defineProps({
    date: { type: Date, required: true },
    videos: { type: Array<VideoAbstract>, default: () => [] },
});

const count = ref({ b: 0, i: 0, e: 0, c: 0 });

watch(() => props.videos, () => {
    count.value.b = 0;
    count.value.i = 0;
    count.value.e = 0;
    count.value.c = 0;
    for (const video of props.videos) {
        if (isStandardLevel(video.level)) count.value[video.level]++;
        else count.value.c++;
    }
}, { immediate: true });

/* 本地化 Localization */
const i18nMessages = {
    'zh-cn': { local: {
        noVideoOnDate: '{0} 无录像',
        uploadedNVideosOnDate: '{0} 共 {1} 个录像',
    } },
    en: { local: {
        noVideoOnDate: 'No video on {0}',
        uploadedNVideosOnDate: '{1} videos on {0}',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style lang="less" scoped>
.dot {
    height: 12px;
    width: 12px;
    border-radius: 50%;
    display: inline-block;
}
</style>
