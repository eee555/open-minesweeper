<template>
    <section class="efficiency-ranking">
        <div class="efficiency-toolbar">
            <strong>{{ t('common.prop.thrp') }}</strong>
            <Tippy>
                <BaseIconInfo />
                <template #content>
                    <div class="card card-small">
                        {{ t('local.rules') }}
                    </div>
                </template>
            </Tippy>
            <Tippy trigger="mouseenter focusin click" :max-width="400">
                <BaseTextButton type="primary" underline="hover">
                    {{ t('local.howToImprove') }}
                </BaseTextButton>
                <template #content>
                    <div class="card card-small">
                        {{ t('local.improve') }}
                    </div>
                </template>
            </Tippy>
            <div class="efficiency-actions">
                <BaseButton class="square-button" data-cy="ranking-color" :type="local.colored ? 'primary' : 'default'" :aria-label="t('common.prop.color')" :title="t('common.prop.color')" :aria-pressed="local.colored" @click="local.colored = !local.colored">
                    <i class="efficiency-color-icon pi pi-palette" aria-hidden="true" />
                </BaseButton>
                <BaseButton class="square-button" data-cy="ranking-refresh" :disabled="!ranking" :aria-label="t('common.action.refresh')" :title="t('common.action.refresh')" @click="ranking?.refresh()">
                    <BaseIconRefresh :loading="ranking?.loading ?? false" aria-hidden="true" />
                </BaseButton>
            </div>
        </div>
        <RouterView v-slot="{ Component }">
            <component :is="Component" ref="ranking" :colored="local.colored" />
        </RouterView>
    </section>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import '@/styles/text.css';
import { useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterView } from 'vue-router';
import { Tippy } from 'vue-tippy';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { BaseIconInfo, BaseIconRefresh } from '@/components/common/icon';
import { local } from '@/store/local';

const ranking = useTemplateRef<{ refresh: () => void | Promise<void>; loading: boolean }>('ranking');
const i18nMessages = {
    'zh-cn': { local: {
        howToImprove: '如何提高成绩',
        rules: '标准模式、已审核且非隐藏比赛录像，每个级别取最高 Thrp（3BV / 有效点击数），不设最低 3BV，不分 NF。总分为三级别之和，缺项计 0；同分优先更早上传的成绩，总分按组合达成时间比较。',
        improve: '上传自己的标准模式通关录像，绑定录像内标识并通过审核。以更少的有效点击完成相同 3BV，或上传 Thrp 更高的录像，可提升对应级别及总分。比赛隐藏录像公开后计入。',
    } },
    en: { local: {
        howToImprove: 'How to improve',
        rules: 'Best Thrp (3BV / effective clicks) per level from official, public Standard replays. No minimum 3BV or separate NF ranking. Sum adds all three levels, with missing results counting as zero. Ties favor earlier uploads; Sum uses the latest upload among its component records.',
        improve: 'Upload your own completed Standard replays, bind their identifiers and have them approved. Use fewer effective clicks for the same 3BV, or upload a higher Thrp to improve that level and your sum. Hidden tournament replays count after they are revealed.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.efficiency-ranking {
    min-width: 0;
}

.efficiency-toolbar,
.efficiency-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.efficiency-toolbar {
    flex-wrap: wrap;
    margin-bottom: 1rem;
}

.efficiency-actions {
    margin-left: auto;
}

.efficiency-color-icon {
    background: linear-gradient(135deg, #e5484d 15%, #c99700 35%, #16a34a 60%, #3b82f6 85%);
    background-clip: text;
    color: transparent;
}
</style>
