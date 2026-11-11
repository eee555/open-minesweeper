<template>
    <div class="account-panel">
        <template v-if="verified">
            <p v-if="!info.name.trim()" class="text-small text-warning">
                {{ t('local.profilePending') }}
            </p>
            <div class="description-layout">
                <dl class="descriptions descriptions-bordered">
                    <div class="description-item">
                        <dt>{{ t('prop.update_time') }}</dt><dd>
                            {{ toISODateTimeString(info.update_time) }}
                        </dd>
                    </div>
                    <div class="description-item">
                        <dt>{{ t('accountlink.msgamesName') }}</dt><dd>
                            {{ info.name }}
                        </dd>
                    </div>
                    <div class="description-item">
                        <dt>{{ t('accountlink.msgamesLocalName') }}</dt><dd>
                            {{ info.local_name }}
                        </dd>
                    </div>
                    <div class="description-item">
                        <dt>{{ t('accountlink.msgamesJoined') }}</dt><dd>
                            {{ info.joined.getTime() ? toISODateTimeString(info.joined) : '--' }}
                        </dd>
                    </div>
                    <div class="description-item">
                        <dt>{{ t('local.country') }}</dt><dd>
                            {{ info.country || '--' }}
                        </dd>
                    </div>
                    <div class="description-item">
                        <dt>{{ t('local.region') }}</dt><dd>
                            {{ info.state || '--' }}
                        </dd>
                    </div>
                    <div class="description-item">
                        <dt>{{ t('local.hand') }}</dt><dd>
                            {{ info.hand || '--' }}
                        </dd>
                    </div>
                    <div class="description-item">
                        <dt>{{ t('local.mouse') }}</dt><dd>
                            {{ info.mouse || '--' }}
                        </dd>
                    </div>
                </dl>
            </div>
            <BaseButton v-if="ownsAccount" size="small" @click="queueVisible = true">
                {{ t('local.videos') }}
            </BaseButton>
            <ElDialog v-if="ownsAccount && queueVisible" v-model="queueVisible" :title="t('local.videos')" width="min(70em, 95vw)" destroy-on-close>
                <MSGamesVideoImportQueue :msgames-id="info.id" :owner="ownsAccount" />
            </ElDialog>
        </template>
        <UnverifiedNotice v-else />
    </div>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import '../page.css';
import { ElDialog } from 'element-plus';
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import MSGamesVideoImportQueue from '@/components/accountlinks/MSGamesVideoImportQueue.vue';
import UnverifiedNotice from '@/components/accountlinks/UnverifiedNotice.vue';
import BaseButton from '@/components/common/BaseButton.vue';
import { store } from '@/store';
import { AccountMSGames } from '@/utils/accountlinks';
import { toISODateTimeString } from '@/utils/datetime';

const props = defineProps({
    verified: { type: Boolean, default: false },
    info: { type: AccountMSGames, default: () => new AccountMSGames() },
});

const queueVisible = ref(false);
// 纪念账号无法登录，管理员在其主页上视同本人；关联账号必须属于当前主页的用户。
const ownsAccount = computed(() => store.user.id > 0 && (
    store.user.id === props.info.parent
    || (store.isMemorialProfileAdmin && store.player.id === props.info.parent)
));
const { t } = useI18n({ messages: {
    'zh-cn': { local: { country: '国家', region: '地区', hand: '惯用手', mouse: '鼠标', videos: '录像列表与导入', profilePending: '账号已绑定，资料暂缺，可稍后刷新。' } },
    en: { local: { country: 'Country', region: 'Region', hand: 'Hand', mouse: 'Mouse', videos: 'Videos and import', profilePending: 'Account linked. Profile details are unavailable; try refreshing later.' } },
} });
</script>
