<template>
    <ElDialog
        v-model="videoplayerstore.visible" style="backdrop-filter: blur(1px); height: fit-content;" align-center destroy-on-close
        :modal="false" :lock-scroll="false" width="fit-content"
    >
        <template #header>
            <div style="display: flex">
                <RouterLink :to="`/video/${videoplayerstore.id}`" class="link video-player__analyzer-link" @click="videoplayerstore.visible = false">
                    {{ t('local.video') }} #{{ videoplayerstore.id }}
                </RouterLink>
            </div>
        </template>
        <NativePlayer :src="videoplayerstore.url" />
    </ElDialog>
</template>

<script setup lang="ts">
import '@/styles/link.css';
import { ElDialog } from 'element-plus';
import { defineAsyncComponent, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink, useRoute } from 'vue-router';

import { videoplayerstore } from '@/store';

const NativePlayer = defineAsyncComponent(() => import('./NativePlayer.vue'));
const route = useRoute();
watch(() => route.fullPath, () => {
    videoplayerstore.visible = false;
});

const i18nMessages = {
    'zh-cn': { local: {
        video: '录像',
    } },
    en: { local: {
        video: 'Video',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-player__analyzer-link {
    color: inherit;
}
</style>
