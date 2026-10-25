<template>
    <section class="card">
        <h2 class="card-title">
            {{ t('local.appearance') }}
        </h2>
        <div class="description-layout">
            <dl class="descriptions">
                <div class="description-item">
                    <dt>{{ t('local.viennaLogo') }}</dt>
                    <dd>
                        <ElSwitch v-model="local.vienna_logo_legacy">
                            <template #active>
                                <img style="width: 16px; height: 16px" :src="ViennaIconLegacy" :title="t('common.old')">
                            </template>
                            <template #inactive>
                                <img style="width: 16px; height: 16px" :src="ViennaIconNew" :title="t('common.new')">
                            </template>
                        </ElSwitch>
                    </dd>
                </div>
                <div class="description-item">
                    <dt>{{ t('local.navigationLayout') }}</dt>
                    <dd>
                        <select v-model="local.navigation_layout" class="navigation-position-setting" data-cy="navigation-layout" :aria-label="t('local.navigationLayout')">
                            <option value="top">
                                {{ t('local.navigationTop') }}
                            </option>
                            <option value="sidebar">
                                {{ t('local.navigationSidebar') }}
                            </option>
                        </select>
                    </dd>
                </div>
                <div class="description-item">
                    <dt>{{ t('local.notificationDuration') }}</dt>
                    <dd>
                        <BaseTooltip>
                            <ElInputNumber v-model="local.notification_duration" size="small" :min="0" :step="1000" />
                            <template #content>
                                <span class="text-regular">
                                    {{ t('local.notificationDurationTooltip1') }}
                                    <br>
                                    {{ t('local.notificationDurationTooltip2') }}
                                </span>
                            </template>
                        </BaseTooltip>
                    </dd>
                </div>
                <div class="description-item description-wide">
                    <dt>{{ t('local.experimentalFeature') }}</dt>
                    <dd>
                        <ElSwitch v-model="local.experimental" />
                    </dd>
                </div>
            </dl>
        </div>
    </section>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import '@/styles/cards.css';
import '@/styles/text.css';

import { ElInputNumber, ElSwitch } from 'element-plus';
import { useI18n } from 'vue-i18n';

import BaseTooltip from '@/components/common/BaseTooltip.vue';
import { local } from '@/store';
import { ViennaIconLegacy, ViennaIconNew } from '@/utils/assets';

const i18nMessages = {
    'zh-cn': { local: {
        appearance: '外观设置',
        experimentalFeature: '实验功能',
        navigationLayout: '导航位置',
        navigationTop: '顶栏',
        navigationSidebar: '侧栏',
        notificationDuration: '通知时长',
        notificationDurationTooltip1: '显示的时间，单位毫秒。',
        notificationDurationTooltip2: '值为0则不会自动关闭。',
        viennaLogo: 'RMV图标',
    } },
    en: { local: {
        appearance: 'Appearance',
        experimentalFeature: 'Experimental Features',
        navigationLayout: 'Navigation position',
        navigationTop: 'Top bar',
        navigationSidebar: 'Side bar',
        notificationDuration: 'Notification Duration',
        notificationDurationTooltip1: 'Duration before close. ',
        notificationDurationTooltip2: 'It will not automatically close if set 0. ',
        viennaLogo: 'RMV logo',
    } },
};

const { t } = useI18n({
    messages: i18nMessages,
});
</script>

<style scoped>
.navigation-position-setting {
    min-height: 28px;
    max-width: 100%;
    border: 1px solid var(--ui-border-color);
    border-radius: 0;
    padding: 3px 8px;
    background: var(--ui-bg-color);
    color: var(--ui-text-color-regular);
    font: inherit;
}

.navigation-position-setting:focus-visible {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: 1px;
}
</style>
