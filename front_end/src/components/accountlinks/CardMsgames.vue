<template>
    <BaseCardNormal>
        <div style="margin-bottom: 0.5em;">
            <PrToolbar>
                <template #start>
                    <span class="text-medium text-regular">
                        {{ t('common.platform.a') }}&nbsp;#{{ id }}
                    </span>
                </template>
            </PrToolbar>
        </div>
        <template v-if="verified">
            <ElDescriptions border>
                <ElDescriptionsItem :label="t('common.prop.update_time')" :span="3">
                    {{ toISODateTimeString(info.update_time) }}
                </ElDescriptionsItem>
                <ElDescriptionsItem :label="t('accountlink.msgamesName')" :span="3">
                    {{ info.name }}
                </ElDescriptionsItem>
                <ElDescriptionsItem :label="t('accountlink.msgamesLocalName')" :span="3">
                    {{ info.local_name }}
                </ElDescriptionsItem>
                <ElDescriptionsItem :label="t('accountlink.msgamesJoined')" :span="3">
                    {{ info.joined.getTime() ? toISODateTimeString(info.joined) : '--' }}
                </ElDescriptionsItem>
                <ElDescriptionsItem :label="t('local.country')" :span="3">
                    {{ info.country || '--' }}
                </ElDescriptionsItem>
                <ElDescriptionsItem :label="t('local.region')" :span="3">
                    {{ info.state || '--' }}
                </ElDescriptionsItem>
                <ElDescriptionsItem :label="t('local.hand')" :span="3">
                    {{ info.hand || '--' }}
                </ElDescriptionsItem>
                <ElDescriptionsItem :label="t('local.mouse')" :span="3">
                    {{ info.mouse || '--' }}
                </ElDescriptionsItem>
            </ElDescriptions>
            <BaseButton v-if="ownsAccount" size="small" @click="queueVisible = true">
                {{ t('local.videos') }}
            </BaseButton>
            <ElDialog v-if="ownsAccount && queueVisible" v-model="queueVisible" :title="t('local.videos')" width="min(70em, 95vw)" destroy-on-close>
                <MSGamesVideoImportQueue :msgames-id="info.id" :owner="ownsAccount" />
            </ElDialog>
        </template>
        <UnverifiedNotice v-else />
    </BaseCardNormal>
</template>

<script setup lang="ts">
import { ElDescriptions, ElDescriptionsItem, ElDialog } from 'element-plus';
import PrToolbar from 'primevue/toolbar';
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import MSGamesVideoImportQueue from './MSGamesVideoImportQueue.vue';
import UnverifiedNotice from './UnverifiedNotice.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import { store } from '@/store';
import { AccountMSGames } from '@/utils/accountlinks';
import { toISODateTimeString } from '@/utils/datetime';

const props = defineProps({
    id: { type: String, default: '' },
    verified: { type: Boolean, default: false },
    info: { type: AccountMSGames, default: () => new AccountMSGames() },
});

const queueVisible = ref(false);
const ownsAccount = computed(() => store.user.id > 0 && store.user.id === props.info.parent);
const { t } = useI18n({ messages: {
    'zh-cn': { local: { country: '国家', region: '地区', hand: '惯用手', mouse: '鼠标', videos: '录像列表与导入' } },
    en: { local: { country: 'Country', region: 'Region', hand: 'Hand', mouse: 'Mouse', videos: 'Videos and import' } },
} });
</script>
