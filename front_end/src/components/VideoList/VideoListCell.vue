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
</template>

<script setup lang="ts">
import { defineAsyncComponent } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { FixedColumnType } from './columns';

import BaseOverlay from '@/components/common/BaseOverlay.vue';
import PlayerName from '@/components/PlayerName.vue';
import GameLevelIcon from '@/components/widgets/GameLevelIcon.vue';
import SoftwareIcon from '@/components/widgets/SoftwareIcon.vue';
import VideoStateIcon from '@/components/widgets/VideoStateIcon.vue';
import { ArbiterIcon, Classic95Icon, MetasweeperIcon } from '@/utils/assets';
import { isStandardLevel } from '@/utils/ms_const';
import type { VideoAbstract } from '@/utils/videoabstract';

defineProps({
    choice: { type: String as PropType<FixedColumnType>, required: true },
    video: { type: Object as PropType<VideoAbstract>, required: true },
});

const { t } = useI18n();

const MetasweeperHelper = defineAsyncComponent(() => import('@/views/ResourcesView/MetasweeperHelper.vue'));
const ArbiterHelper = defineAsyncComponent(() => import('@/views/ResourcesView/ArbiterHelper.vue'));
</script>
