<template>
    <div class="account-panel">
        <div class="description-layout">
            <dl class="descriptions descriptions-bordered">
                <div class="description-item">
                    <dt>{{ t('prop.update_time') }}</dt><dd>
                        {{ toISODateTimeString(info.update_time) }}
                    </dd>
                </div>
            </dl>
        </div>
        <p class="classic-hint text-regular">
            {{ t('local.unlinkHint') }}
        </p>
    </div>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import '../page.css';

import { useI18n } from 'vue-i18n';

import { AccountClassic } from '@/utils/accountlinks';
import { toISODateTimeString } from '@/utils/datetime';

defineProps({
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
