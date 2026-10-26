<template>
    <BaseCardNormal>
        <div style="margin-bottom: 0.5em;">
            <PrToolbar>
                <template #start>
                    <span class="text-medium text-regular">
                        {{ t('platform.c') }}&nbsp;#{{ id }}
                    </span>
                </template>
                <template #end>
                    <CarouselControl :ref-carousel="refCarousel!" :length="carouselLength" />
                </template>
            </PrToolbar>
        </div>
        <ElCarousel v-if="verified" ref="refCarousel" trigger="click" :autoplay="false" indicator-position="none" :loop="false" arrow="never">
            <ElCarouselItem>
                <ElDescriptions border>
                    <ElDescriptionsItem :label="t('prop.update_time')" :span="3">
                        {{ toISODateTimeString(info.update_time) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.name')" :span="3">
                        {{ info.name }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.totalViews')" :span="3">
                        {{ info.total_views }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('level.b')" :span="3">
                        {{ cs_to_s(info.b_t_ms! / 10) }}
                        &nbsp;|&nbsp;
                        {{ cs_to_s(info.b_b_cent!) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('level.i')" :span="3">
                        {{ cs_to_s(info.i_t_ms! / 10) }}
                        &nbsp;|&nbsp;
                        {{ cs_to_s(info.i_b_cent!) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('level.e')" :span="3">
                        {{ cs_to_s(info.e_t_ms! / 10) }}
                        &nbsp;|&nbsp;
                        {{ cs_to_s(info.e_b_cent!) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('level.sum')">
                        {{ cs_to_s(info.sum_t_ms / 10) }}
                        &nbsp;|&nbsp;
                        {{ cs_to_s(info.sum_b_cent) }}
                    </ElDescriptionsItem>
                </ElDescriptions>
            </ElCarouselItem>
            <ElCarouselItem style="display: flex; flex-direction: column;">
                <div>
                    <span class="text-medium text-regular">
                        {{ t('accountlink.statSummary') }}
                    </span>
                    &nbsp;
                    <ElButton disabled>
                        {{ t('accountlink.synchronize') }}
                    </ElButton>
                </div>
                <div class="text-regular text-small" style="margin-bottom: auto; margin-top: 0.25em;">
                    {{ t('local.crawlingDisabled') }}
                </div>
                <div style="margin-bottom: 0.25em">
                    <span class="text-medium text-regular">
                        {{ t('accountlink.synchronizeVideos') }}
                    </span>
                    <BaseOverlay>
                        <BaseIconInfo />
                        <template #header>
                            扫雷网录像同步功能
                        </template>
                        <template #overlay>
                            <SaoleiImportHelper />
                        </template>
                    </BaseOverlay>
                </div>
                <div class="text-regular">
                    已收藏{{ importSummary.total }}个录像
                    &nbsp;
                    <ElLink disabled underline="never" style="vertical-align: top;">
                        {{ syncModeAll ? t('accountlink.synchronizeAll') : t('accountlink.synchronizeNew') }}
                    </ElLink>
                    <ElButton disabled class="button-compact">
                        更新
                    </ElButton>
                    &nbsp;
                    <ElButton class="button-compact" @click="importQueueVisible = true">
                        {{ t('accountlink.synchronizeManage') }}
                    </ElButton>
                </div>
                <div class="text-regular" style="margin-top: 0.25em">
                    <StackBar :data="stackBarData" legend />
                </div>
                <div class="text-regular" style="margin-top: 0.5em">
                    新收藏{{ importSummary.new_total }}个录像
                </div>
                <div class="text-regular" style="margin-top: 0.25em">
                    <StackBar :data="stackBarNewData" legend />
                </div>
                <!-- 后端暂时有bug，删不掉 -->
                <!-- <div style="margin-top: auto">
                    <el-button type="danger" plain disabled @click="deleteDialogVisible = true; confirmSaoleiId = ''">
                        {{ t('accountlink.deleteLink') }}
                    </el-button>
                </div> -->
            </ElCarouselItem>
        </ElCarousel>
        <UnverifiedNotice v-else />

        <ElDialog v-model="importQueueVisible" destroy-on-close style="width: 50em">
            <VideoImportQueue :saolei-id="info.id" />
        </ElDialog>
    </BaseCardNormal>

    <ElDialog v-model="deleteDialogVisible" title="请输入扫雷网ID" style="width: 15em">
        <ElInput v-model="confirmSaoleiId" style="width: 7.8em" />
        &nbsp;
        <ElButton :disabled="confirmSaoleiId != info.id.toString()" type="danger" plain @click="deleteAccountLink">
            确认解除
        </ElButton>
    </ElDialog>
</template>

<script setup lang="ts">
import 'vue-data-ui/style.css';
import '@/styles/button.css';

import { ElButton, ElCarousel, ElCarouselItem, ElDescriptions, ElDescriptionsItem, ElDialog, ElInput, ElLink } from 'element-plus';
import PrToolbar from 'primevue/toolbar';
import { computed, ref, useTemplateRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import CarouselControl from './CarouselControl.vue';
import UnverifiedNotice from './UnverifiedNotice.vue';
import VideoImportQueue from './VideoImportQueue.vue';

import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import BaseOverlay from '@/components/common/BaseOverlay.vue';
import { BaseIconInfo } from '@/components/common/icon';
import SaoleiImportHelper from '@/components/dialogs/SaoleiImportHelper.vue';
import { httpErrorNotification } from '@/components/Notifications';
import StackBar from '@/components/visualization/StackBar/App.vue';
import { store } from '@/store';
import { cs_to_s } from '@/utils';
import { AccountSaolei, SaoleiImportSummaryDefault } from '@/utils/accountlinks';
import type { SaoleiImportSummary } from '@/utils/accountlinks';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { toISODateTimeString } from '@/utils/datetime';

const props = defineProps({
    id: { type: String, default: '0' },
    verified: { type: Boolean, default: false },
    info: { type: AccountSaolei, default: () => new AccountSaolei() },
});

const emit = defineEmits(['refresh']);

const { proxy } = useCurrentInstance();

const refCarousel = useTemplateRef<typeof ElCarousel>('refCarousel');
const deleteDialogVisible = ref(false);
const importQueueVisible = ref(false);
const confirmSaoleiId = ref('');
const syncModeAll = ref(false);
const carouselLength = computed(() => (store.player.id == store.user.id ? 2 : 1));

function deleteAccountLink() {
    proxy.$axios.post('/accountlink/delete/', {
        platform: 'c',
    }).then(() => {
        emit('refresh');
    }).catch(httpErrorNotification);
    deleteDialogVisible.value = false;
}

const importSummary = ref<SaoleiImportSummary>(SaoleiImportSummaryDefault);
const stackBarData = computed(() => [
    { name: t('accountlink.importStatus.successful'), color: '#34d399', value: importSummary.value.old_imported + importSummary.value.new_success },
    { name: t('accountlink.importStatus.running'), color: '#fbbf24', value: importSummary.value.new_total - importSummary.value.new_success - importSummary.value.new_ready - importSummary.value.new_failed - importSummary.value.new_connection },
    { name: t('accountlink.importStatus.ready'), color: '#60a5fa', value: importSummary.value.new_ready },
    { name: t('accountlink.importStatus.connection'), color: '#c084fc', value: importSummary.value.new_connection },
    { name: t('accountlink.importStatus.failed'), color: '#f43f5e', value: importSummary.value.new_failed },
]);
const stackBarNewData = computed(() => [
    { name: t('accountlink.importStatus.successful'), color: '#34d399', value: importSummary.value.new_success },
    { name: t('accountlink.importStatus.running'), color: '#fbbf24', value: importSummary.value.new_total - importSummary.value.new_success - importSummary.value.new_ready - importSummary.value.new_failed - importSummary.value.new_connection },
    { name: t('accountlink.importStatus.ready'), color: '#60a5fa', value: importSummary.value.new_ready },
    { name: t('accountlink.importStatus.connection'), color: '#c084fc', value: importSummary.value.new_connection },
    { name: t('accountlink.importStatus.failed'), color: '#f43f5e', value: importSummary.value.new_failed },
]);

async function getImportSummary() {
    if (props.info.id == 0) return;
    await proxy.$axios.get('/accountlink/saolei/videoimport/stat/', {
        params: {
            saolei_id: props.info.id,
        },
    }).then((response) => {
        importSummary.value = response.data;
    }).catch(httpErrorNotification);
}

watch(() => props.info.id, getImportSummary, { immediate: true });

/* 本地化 Localization */
const i18nMessage = {
    'zh-cn': { local: {
        name: '姓名',
        totalViews: '综合人气',
        videoCount: '录像数量',
        crawlingDisabled: '扫雷网正在迁移，资料刷新和录像同步已关闭。账号关联和已保存的数据仍然保留。',
    } },
    en: { local: {
        name: 'Name',
        totalViews: 'Total Views',
        videoCount: 'Video Count',
        crawlingDisabled: 'Profile refresh and replay synchronization are disabled while Saolei.wang migrates. Account links and saved data remain available.',
    } },
};

const { t } = useI18n({ messages: i18nMessage });
</script>
