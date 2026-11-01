<template>
    <BaseCardNormal>
        <PrToolbar style="margin-bottom: 0.5em">
            <template #start>
                <span class="text-medium text-regular">{{ t('platform.c') }}&nbsp;#{{ id }}</span>
            </template>
            <template #end>
                <CarouselControl :ref-carousel="refCarousel!" :length="ownsAccount ? 2 : 1" />
            </template>
        </PrToolbar>
        <ElCarousel v-if="verified" ref="refCarousel" trigger="click" :autoplay="false" indicator-position="none" :loop="false" arrow="never">
            <ElCarouselItem>
                <ElDescriptions border>
                    <ElDescriptionsItem :label="t('prop.update_time')" :span="3">
                        {{ toISODateTimeString(info.update_time) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.name')" :span="3">
                        {{ info.name }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.catalogueUpdated')" :span="3">
                        {{ summary.video_update_time ? toISODateTimeString(new Date(summary.video_update_time)) : '--' }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.collected')" :span="3">
                        {{ summary.total }}
                    </ElDescriptionsItem>
                </ElDescriptions>
                <BaseButton size="small" @click="queueVisible = true">
                    {{ t('accountlink.synchronizeManage') }}
                </BaseButton>
                <BaseButton v-if="ownsAccount" size="small" :loading="refreshing" @click="refreshProfile">
                    {{ t('local.refreshProfile') }}
                </BaseButton>
            </ElCarouselItem>
            <ElCarouselItem v-if="ownsAccount" style="display: flex; flex-direction: column; gap: 0.5em">
                <label class="text-regular">
                    <ElSwitch :model-value="autoSync" :disabled="saving" data-cy="saolei-auto-sync" @change="toggleAutoSync" />
                    {{ t('local.autoSync') }}
                </label>
                <span class="text-regular text-small">{{ t('local.autoHint') }}</span>
                <div>
                    <BaseButton size="small" @click="queueVisible = true">
                        {{ t('local.manualSync') }}
                    </BaseButton>
                    <BaseOverlay>
                        <BaseIconInfo />
                        <template #header>
                            {{ t('accountlink.synchronizeVideos') }}
                        </template>
                        <template #overlay>
                            <SaoleiImportHelper />
                        </template>
                    </BaseOverlay>
                </div>
                <StackBar :data="stackBarData" legend />
            </ElCarouselItem>
        </ElCarousel>
        <UnverifiedNotice v-else />
        <ElDialog v-if="queueVisible" v-model="queueVisible" destroy-on-close width="min(70em, 95vw)" :title="t('accountlink.synchronizeManage')" @closed="refreshSummary">
            <VideoImportQueue :saolei-id="info.id" :owner="ownsAccount" />
        </ElDialog>
    </BaseCardNormal>
</template>

<script setup lang="ts">
import 'vue-data-ui/style.css';

import { ElCarousel, ElCarouselItem, ElDescriptions, ElDescriptionsItem, ElDialog, ElSwitch } from 'element-plus';
import PrToolbar from 'primevue/toolbar';
import { computed, ref, useTemplateRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import CarouselControl from './CarouselControl.vue';
import UnverifiedNotice from './UnverifiedNotice.vue';
import VideoImportQueue from './VideoImportQueue.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import BaseOverlay from '@/components/common/BaseOverlay.vue';
import { BaseIconInfo } from '@/components/common/icon';
import SaoleiImportHelper from '@/components/dialogs/SaoleiImportHelper.vue';
import { httpErrorNotification } from '@/components/Notifications';
import StackBar from '@/components/visualization/StackBar/App.vue';
import { fetchSaoleiSummary, refreshSaoleiProfile, setSaoleiAutoSync } from '@/services/saoleiSyncService';
import { store } from '@/store';
import { AccountSaolei, SaoleiImportSummaryDefault } from '@/utils/accountlinks';
import { toISODateTimeString } from '@/utils/datetime';

const props = defineProps({
    id: { type: String, default: '0' },
    verified: { type: Boolean, default: false },
    info: { type: AccountSaolei, default: () => new AccountSaolei() },
});
const emit = defineEmits(['refresh']);
const refCarousel = useTemplateRef<typeof ElCarousel>('refCarousel');
const queueVisible = ref(false);
const saving = ref(false);
const refreshing = ref(false);
const autoSync = ref(props.info.auto_sync);
const ownsAccount = computed(() => store.user.id > 0 && store.user.id === props.info.parent);
const summary = ref({ ...SaoleiImportSummaryDefault });
const stackBarData = computed(() => [
    { name: t('local.imported'), color: '#34d399', value: summary.value.imported },
    { name: t('local.pending'), color: '#60a5fa', value: summary.value.pending },
    { name: t('local.rejected'), color: '#f43f5e', value: summary.value.rejected },
    { name: t('local.skipped'), color: '#9ca3af', value: summary.value.skipped },
]);

async function refreshSummary() {
    const { id } = props.info;
    if (!props.verified || !id) return;
    try {
        const data = await fetchSaoleiSummary(id);
        if (id !== props.info.id) return;
        summary.value = data;
        autoSync.value = data.auto_sync;
    } catch (error) {
        httpErrorNotification(error);
    }
}

async function toggleAutoSync(value: string | number | boolean) {
    saving.value = true;
    try {
        const data = await setSaoleiAutoSync(props.info.id, Boolean(value));
        autoSync.value = data.auto_sync;
        emit('refresh');
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        saving.value = false;
    }
}

async function refreshProfile() {
    refreshing.value = true;
    try {
        await refreshSaoleiProfile(props.info.id); emit('refresh');
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        refreshing.value = false;
    }
}

watch(() => [props.info.id, props.verified] as const, () => {
    queueVisible.value = false;
    summary.value = { ...SaoleiImportSummaryDefault };
    autoSync.value = props.info.auto_sync;
    void refreshSummary();
}, { immediate: true });

const { t } = useI18n({ messages: {
    'zh-cn': { local: {
        name: '姓名',
        catalogueUpdated: '目录更新时间',
        collected: '已收藏录像',
        refreshProfile: '刷新资料',
        autoSync: '自动同步目录和录像',
        autoHint: '每日更新目录，每小时最多导入100个录像。关闭后仍可手动同步。',
        manualSync: '手动同步与导入',
        imported: '已导入',
        pending: '待导入',
        rejected: '本站拒收',
        skipped: '不支持的软件',
    } },
    en: { local: {
        name: 'Name',
        catalogueUpdated: 'Catalogue updated',
        collected: 'Collected replays',
        refreshProfile: 'Refresh profile',
        autoSync: 'Automatic catalogue and replay sync',
        autoHint: 'The catalogue updates daily; up to 100 replays are imported each hour. Manual sync remains available when disabled.',
        manualSync: 'Manual sync and import',
        imported: 'Imported',
        pending: 'Pending',
        rejected: 'Rejected locally',
        skipped: 'Unsupported software',
    } },
} });
</script>
