<template>
    <div class="account-panel">
        <div v-if="verified" class="account-sections">
            <section class="account-section">
                <div class="description-layout">
                    <dl class="descriptions descriptions-bordered">
                        <div class="description-item">
                            <dt>{{ t('prop.update_time') }}</dt><dd>
                                {{ toISODateTimeString(info.update_time) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.name') }}</dt><dd>
                                {{ info.name }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.catalogueUpdated') }}</dt><dd>
                                {{ summary.video_update_time ? toISODateTimeString(new Date(summary.video_update_time)) : '--' }}
                            </dd>
                        </div>
                    </dl>
                </div>
                <BaseButton size="small" @click="queueVisible = true">
                    {{ t('local.videos') }}
                </BaseButton>
                <BaseButton v-if="ownsAccount" size="small" :loading="refreshing" @click="refreshProfile">
                    {{ t('local.refreshProfile') }}
                </BaseButton>
            </section>
            <section v-if="ownsAccount" class="account-section">
                <label class="switch" :title="t('local.autoSyncHint')">
                    <input class="switch-input" type="checkbox" role="switch" :checked="autoSync" :disabled="saving" data-cy="saolei-auto-sync" @change="toggleAutoSync">
                    <span class="switch-track" aria-hidden="true" />
                    {{ t('local.autoSync') }}
                </label>
                <StackBar :data="stackBarData" legend />
            </section>
        </div>
        <UnverifiedNotice v-else />
        <ElDialog v-if="queueVisible" v-model="queueVisible" destroy-on-close width="min(70em, 95vw)" :title="t('local.videos')" @closed="refreshSummary">
            <VideoImportQueue :saolei-id="info.id" :owner="ownsAccount" />
        </ElDialog>
    </div>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import '../page.css';
import 'vue-data-ui/style.css';

import { ElDialog } from 'element-plus';
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { useActivePanel } from '../useActivePanel';

import UnverifiedNotice from '@/components/accountlinks/UnverifiedNotice.vue';
import VideoImportQueue from '@/components/accountlinks/VideoImportQueue.vue';
import BaseButton from '@/components/common/BaseButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import StackBar from '@/components/visualization/StackBar/App.vue';
import { fetchSaoleiSummary, refreshSaoleiProfile, setSaoleiAutoSync } from '@/services/saoleiSyncService';
import { store } from '@/store';
import { AccountSaolei, SaoleiImportSummaryDefault } from '@/utils/accountlinks';
import { toISODateTimeString } from '@/utils/datetime';

const props = defineProps({
    verified: { type: Boolean, default: false },
    info: { type: AccountSaolei, default: () => new AccountSaolei() },
});
const emit = defineEmits(['refresh']);
const queueVisible = ref(false);
const isActive = useActivePanel();
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
        if (!isActive() || id !== props.info.id) return;
        summary.value = data;
        autoSync.value = data.auto_sync;
    } catch (error) {
        if (isActive()) httpErrorNotification(error);
    }
}

async function toggleAutoSync(event: Event) {
    const input = event.target as HTMLInputElement;
    const enabled = input.checked;
    input.checked = autoSync.value;
    if (saving.value) return;
    saving.value = true;
    try {
        const data = await setSaoleiAutoSync(props.info.id, enabled);
        if (!isActive()) return;
        autoSync.value = data.auto_sync;
        emit('refresh');
    } catch (error) {
        if (isActive()) httpErrorNotification(error);
    } finally {
        saving.value = false;
    }
}

async function refreshProfile() {
    refreshing.value = true;
    try {
        await refreshSaoleiProfile(props.info.id);
        if (isActive()) emit('refresh');
    } catch (error) {
        if (isActive()) httpErrorNotification(error);
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
        videos: '录像列表',
        refreshProfile: '刷新资料',
        autoSync: '自动同步目录和录像',
        autoSyncHint: '已绑定账号默认每日更新目录，每小时最多自动导入100个录像，可自行关闭。',
        imported: '已导入',
        pending: '待导入',
        rejected: '本站拒收',
        skipped: '不支持的软件',
    } },
    en: { local: {
        name: 'Name',
        catalogueUpdated: 'Catalogue updated',
        videos: 'Replay list',
        refreshProfile: 'Refresh profile',
        autoSync: 'Automatic catalogue and replay sync',
        autoSyncHint: 'Linked accounts update their catalogue daily and import up to 100 replays each hour by default. You can disable this.',
        imported: 'Imported',
        pending: 'Pending',
        rejected: 'Rejected locally',
        skipped: 'Unsupported software',
    } },
} });
</script>
