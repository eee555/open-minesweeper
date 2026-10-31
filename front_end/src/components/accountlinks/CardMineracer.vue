<template>
    <BaseCardNormal>
        <div style="margin-bottom: 0.5em;">
            <PrToolbar>
                <template #start>
                    <span class="text-medium text-regular">
                        {{ t('platform.m') }}&nbsp;#{{ id }}
                    </span>
                </template>
            </PrToolbar>
        </div>
        <ElDescriptions border>
            <ElDescriptionsItem :label="t('prop.update_time')" :span="3">
                {{ toISODateTimeString(info.update_time) }}
            </ElDescriptionsItem>
        </ElDescriptions>
    </BaseCardNormal>
</template>

<script setup lang="ts">
import { ElDescriptions, ElDescriptionsItem } from 'element-plus';
import PrToolbar from 'primevue/toolbar';
import { useI18n } from 'vue-i18n';

import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import { AccountMineracer } from '@/utils/accountlinks';
import { toISODateTimeString } from '@/utils/datetime';

defineProps({
    id: { type: String, default: '' },
    info: { type: AccountMineracer, default: () => new AccountMineracer() },
});

const { t } = useI18n();
</script>
