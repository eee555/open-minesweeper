<template>
    <VideoStateIcon v-if="choice === 'state'" :state="video.state" />
    <PlayerName v-else-if="choice === 'player'" class="name" :user-id="video.player_id" />
    <BaseOverlay v-else-if="choice === 'software'">
        <SoftwareIcon :software="video.software" />
        <template #header>
            <template v-if="video.software === 'e'">
                <img style="width: 24px; height: 24px; vertical-align: middle;" :src="MetasweeperIcon">
                {{ t('software.metasweeper') }}
            </template>
            <template v-else-if="video.software === 'a'">
                <img style="width: 24px; height: 24px; vertical-align: middle;" :src="ArbiterIcon">
                {{ t('software.arbiter') }}
            </template>
            <template v-else-if="video.software === 'x'">
                <img style="width: 24px; height: 24px; vertical-align: middle;" :src="Classic95Icon">
                {{ t('softwareName.x') }}
            </template>
        </template>
        <template #overlay>
            <MetasweeperHelper v-if="video.software === 'e'" style="justify-self: center;" />
            <ArbiterHelper v-else-if="video.software === 'a'" style="justify-self: center;" />
        </template>
    </BaseOverlay>
    <span v-else-if="choice === 'mode'" class="text">{{ t(`mode.code${video.mode}`) }}</span>
    <span v-else-if="choice === 'level'" class="video-list__cell">
        <span v-if="video.isLocal && !isStandardLevel(video.level)">—</span>
        <GameLevelIcon v-else :level="video.level" />
    </span>
    <span v-else-if="choice === 'upload_time'" class="text">{{ video.isLocal ? '—' : utc_to_local_format(video.upload_time) }}</span>
    <span v-else-if="choice === 'end_time'" class="text">{{ utc_to_local_format(video.end_time) }}</span>
    <span v-else-if="choice === 'file_size'" class="text">{{ fileSizeText }}</span>
    <span v-else class="text">{{ stat === null ? '—' : video.displayStat(stat) }}</span>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { isStatKey } from './videoListData';

import BaseOverlay from '@/components/common/BaseOverlay.vue';
import PlayerName from '@/components/PlayerName.vue';
import GameLevelIcon from '@/components/widgets/GameLevelIcon.vue';
import SoftwareIcon from '@/components/widgets/SoftwareIcon.vue';
import VideoStateIcon from '@/components/widgets/VideoStateIcon.vue';
import { ArbiterIcon, Classic95Icon, MetasweeperIcon } from '@/utils/assets';
import type { ColumnChoice } from '@/utils/ms_const';
import { isStandardLevel } from '@/utils/ms_const';
import { formatBytes } from '@/utils/strings';
import { utc_to_local_format } from '@/utils/system/tools';
import type { VideoAbstract } from '@/utils/videoabstract';

const props = defineProps({
    choice: { type: String as PropType<ColumnChoice>, required: true },
    video: { type: Object as PropType<VideoAbstract>, required: true },
});

const { t } = useI18n();

const MetasweeperHelper = defineAsyncComponent(() => import('@/views/ResourcesView/MetasweeperHelper.vue'));
const ArbiterHelper = defineAsyncComponent(() => import('@/views/ResourcesView/ArbiterHelper.vue'));

const stat = computed(() => {
    if (!isStatKey(props.choice)) return null;
    return props.choice;
});
const fileSizeText = computed(() => {
    if (props.video.isLocal) return '—';
    if (props.video.file_size === 0) return '-';
    return formatBytes(props.video.file_size);
});
</script>
