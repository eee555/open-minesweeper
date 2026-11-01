<template>
    <ElDialog
        v-model="videoplayerstore.visible" style="backdrop-filter: blur(1px); height: fit-content;" align-center destroy-on-close
        :modal="false" :lock-scroll="false" width="fit-content"
    >
        <template #header>
            <div class="video-player__header">
                <RouterLink :to="`/video/${videoplayerstore.id}`" class="link video-player__analyzer-link" @click="videoplayerstore.visible = false">
                    {{ t('local.video') }} #{{ videoplayerstore.id }}
                </RouterLink>
                <dl v-if="identifiers" class="text text-small video-player__identifiers">
                    <dt class="text-secondary">
                        {{ t('prop.identifier') }}
                    </dt>
                    <dd class="video-player__identifier">
                        <IdentifierText v-if="identifiers.identifier" :text="identifiers.identifier" />
                        <span v-else>—</span>
                    </dd>
                    <dt class="text-secondary">
                        {{ t('local.tournamentIdentifier') }}
                    </dt>
                    <dd class="video-player__tournament-identifier">
                        <template v-if="identifiers.tournament_identifier.length">
                            <IdentifierText v-for="(text, index) in identifiers.tournament_identifier" :key="index" :text="text" />
                        </template>
                        <span v-else>—</span>
                    </dd>
                </dl>
            </div>
        </template>
        <NativePlayer :src="videoplayerstore.url" />
    </ElDialog>
</template>

<script setup lang="ts">
import '@/styles/link.css';
import { ElDialog } from 'element-plus';
import { defineAsyncComponent, shallowRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink, useRoute } from 'vue-router';

import IdentifierText from '@/components/widgets/IdentifierText.vue';
import { fetchVideoInfo } from '@/services/videoInfoService';
import type { ParsedVideoInfo } from '@/services/videoInfoService';
import { videoplayerstore } from '@/store';

const NativePlayer = defineAsyncComponent(() => import('./NativePlayer.vue'));
const identifiers = shallowRef<Pick<ParsedVideoInfo, 'identifier' | 'tournament_identifier'> | null>(null);
watch(() => [videoplayerstore.id, videoplayerstore.visible] as const, ([id, visible], _previous, onCleanup) => {
    let active = true;
    onCleanup(() => {
        active = false;
    });
    identifiers.value = null;
    if (!visible || id <= 0) return;
    void fetchVideoInfo(id).then((video) => {
        if (active) identifiers.value = video;
    }).catch(() => {
        // Identifier loading must not prevent playback; NativePlayer reports replay errors.
    });
}, { immediate: true, flush: 'sync' });
const route = useRoute();
watch(() => route.fullPath, () => {
    videoplayerstore.visible = false;
});

const i18nMessages = {
    'zh-cn': { local: {
        video: '录像',
        tournamentIdentifier: '比赛标识',
    } },
    en: { local: {
        video: 'Video',
        tournamentIdentifier: 'Tournament identifier',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-player__header {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    min-width: 0;
}
.video-player__analyzer-link {
    flex: none;
    color: inherit;
}
.video-player__identifiers {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: baseline;
    gap: 2px 6px;
    flex: 1 1 0;
    width: 0;
    min-width: 0;
}
.video-player__identifiers dd {
    min-width: 0;
    margin: 0;
}
.video-player__tournament-identifier {
    display: flex;
    flex-wrap: wrap;
    gap: 0 8px;
}
</style>
