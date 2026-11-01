<template>
    <BaseCardNormal>
        <div style="margin-bottom: 0.5em;">
            <PrToolbar>
                <template #start>
                    <span class="text-medium text-regular">
                        {{ t('platform.x') }}&nbsp;#{{ id }}
                    </span>
                </template>
            </PrToolbar>
        </div>
        <ElDescriptions border>
            <ElDescriptionsItem :label="t('prop.update_time')" :span="3">
                {{ toISODateTimeString(info.update_time) }}
            </ElDescriptionsItem>
        </ElDescriptions>
        <p class="classic-hint text-regular">
            {{ t('local.unlinkHint') }}
        </p>
    </BaseCardNormal>
</template>

<script setup lang="ts">
import { ElDescriptions, ElDescriptionsItem } from 'element-plus';
import PrToolbar from 'primevue/toolbar';
import { useI18n } from 'vue-i18n';

import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import { AccountClassic } from '@/utils/accountlinks';
import { toISODateTimeString } from '@/utils/datetime';

defineProps({
    id: { type: Number, default: 0 },
    info: { type: AccountClassic, default: () => new AccountClassic() },
});

const i18nMessages = {
    'zh-cn': { local: {
        unlinkHint: '如需解除关联，请在「95经典扫雷」小游戏的荣誉页解绑。',
    } },
    en: { local: {
        unlinkHint: 'To unlink, remove this app from the honours page of the 95 Classic Minesweeper mini game.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style lang="less" scoped>
.classic-hint {
    margin: 0.5rem 0 0;
}
</style>
