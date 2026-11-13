<template>
    <section class="works-page">
        <div class="media-toolbar works-actions">
            <span v-if="loading" class="text-secondary text-small">{{ t('local.loading') }}</span>
            <BaseButton size="small" type="primary" data-cy="open-submit" @click="dialogOpen = true">
                {{ t('local.submit') }}
            </BaseButton>
            <BaseButton
                size="small" class="square-button" :title="t('local.refresh')"
                :aria-label="t('local.refresh')" data-cy="refresh-works" @click="refreshWorks"
            >
                <template #icon>
                    <BaseIconRefresh />
                </template>
            </BaseButton>
        </div>
        <MediaListPanel ref="worksTable" @loading="loading = $event" />
        <SubmitMediaDialog v-if="dialogOpen" @close="dialogOpen = false" @submitted="onSubmitted" />
    </section>
</template>

<script setup lang="ts">
import { ElNotification } from 'element-plus';
import { ref, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { BaseIconRefresh } from '@/components/common/icon';
import MediaListPanel from '@/components/media/MediaListPanel.vue';
import SubmitMediaDialog from '@/components/media/SubmitMediaDialog.vue';
import type { MediaItem } from '@/services/mediaService';

import '@/components/media/media.css';

const worksTable = useTemplateRef<{ refresh?: () => void }>('worksTable');
const dialogOpen = ref(false);
const loading = ref(false);

function refreshWorks(): void {
    worksTable.value?.refresh?.();
}

function onSubmitted(media: MediaItem): void {
    dialogOpen.value = false;
    ElNotification({
        title: t('local.submitDone'),
        message: media.metadata_pending ? t('local.degradedHint') : t('local.normalHint'),
        type: 'success',
    });
    refreshWorks();
}

const i18nMessages = {
    'zh-cn': { local: {
        submit: '投稿',
        refresh: '刷新',
        loading: '加载中',
        submitDone: '投稿成功',
        normalHint: '作品已进入审核队列，可在个人主页查看',
        degradedHint: '投稿已保留，标题由管理员审核时补全并核验外站账号',
    } },
    en: { local: {
        submit: 'Submit',
        refresh: 'Refresh',
        loading: 'Loading',
        submitDone: 'Submitted',
        normalHint: 'Your work is in the review queue; find it on your profile',
        degradedHint: 'Submission kept; a moderator will fill in the title and verify the external account',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped lang="css">
.works-actions {
    justify-content: flex-end;
}
</style>
