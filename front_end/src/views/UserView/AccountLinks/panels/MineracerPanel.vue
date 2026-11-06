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
    </div>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import '../page.css';

import { useI18n } from 'vue-i18n';

import { AccountMineracer } from '@/utils/accountlinks';
import { toISODateTimeString } from '@/utils/datetime';

defineProps({
    info: { type: AccountMineracer, default: () => new AccountMineracer() },
});

const { t } = useI18n();
</script>
