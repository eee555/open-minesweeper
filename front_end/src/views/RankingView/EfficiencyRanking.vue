<template>
    <section class="efficiency-ranking">
        <div class="efficiency-toolbar">
            <ElSelect v-model="selectedRankingName" :aria-label="t('local.rankingName')" class="efficiency-selector">
                <ElOption v-for="name in rankingNames" :key="name" :label="t(`local.label.${name}`)" :value="name" />
            </ElSelect>
            <Tippy>
                <BaseIconInfo />
                <template #content>
                    <div class="card card-small">
                        {{ t(`local.rules.${selectedRankingName}`) }}
                    </div>
                </template>
            </Tippy>
            <Tippy trigger="mouseenter focusin click" :max-width="400">
                <BaseTextButton type="primary" underline="hover">
                    {{ t('local.howToImprove') }}
                </BaseTextButton>
                <template #content>
                    <div class="card card-small">
                        {{ t(`local.improve.${selectedRankingName}`) }}
                    </div>
                </template>
            </Tippy>
            <div class="efficiency-actions">
                <BaseButton class="square-button" data-cy="ranking-color" :type="local.colored ? 'primary' : 'default'" :aria-label="t('prop.color')" :title="t('prop.color')" :aria-pressed="local.colored" @click="local.colored = !local.colored">
                    <i class="efficiency-color-icon pi pi-palette" aria-hidden="true" />
                </BaseButton>
                <BaseButton class="square-button" data-cy="ranking-refresh" :disabled="!ranking" :aria-label="t('action.refresh')" :title="t('action.refresh')" @click="ranking?.refresh()">
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
import { ElOption, ElSelect } from 'element-plus';
import { computed, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterView, useRoute, useRouter } from 'vue-router';
import { Tippy } from 'vue-tippy';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { BaseIconInfo, BaseIconRefresh } from '@/components/common/icon';
import { local } from '@/store/local';

const ranking = useTemplateRef<{ refresh: () => void | Promise<void>; loading: boolean }>('ranking');
const rankingNames = ['thrp', 'nf_ioe'] as const;
const route = useRoute();
const router = useRouter();
const selectedRankingName = computed<typeof rankingNames[number]>({
    get: () => rankingNames.find((name) => route.name === `ranking_efficiency_${name}`) ?? 'thrp',
    set: (name) => {
        void router.push({ name: `ranking_efficiency_${name}` });
    },
});
const i18nMessages = {
    'zh-cn': { local: {
        rankingName: '大榜',
        label: { thrp: '@:prop.thrp', nf_ioe: 'NF IOE' },
        howToImprove: '如何提高成绩',
        rules: {
            thrp: '标准模式、已审核且非隐藏比赛录像，每个级别取最高 Thrp（3BV / 有效点击数），不设最低 3BV。总分为三级别之和，缺项计 0；普通四项同分优先更早上传或达成。高级 NF 独立排序：未满分按 Thrp，满分按达成局数，同 BV 的多局分别计数，不参与总分。',
            nf_ioe: '标准模式、已审核且非隐藏比赛的 NF 录像，不设最低 3BV。每级别取最高 IOE（3BV / 实际点击数），满分 1 时比较用时；总分为三级别之和，缺项计 0，满分 3 时只比较高级用时。括号内为参与比较的秒数。',
        },
        improve: {
            thrp: '上传自己的标准模式通关录像，绑定录像内标识并通过审核。以更少的有效点击完成相同 3BV，或上传 Thrp 更高的录像，可提升对应级别及总分。高级 NF 达到 Thrp=1 后，上传更多满分 NF 录像可提升排名。比赛隐藏录像公开后计入。',
            nf_ioe: '上传自己的标准模式 NF 通关录像，绑定标识并通过审核。减少完成相同 3BV 的实际点击数以提高 IOE；达到 1 后上传用时更短的满分录像。三级别全部满分后，改善高级用时可提升总分榜排名。隐藏比赛录像公开后计入。',
        },
    } },
    en: { local: {
        rankingName: 'Ranking',
        label: { thrp: '@:prop.thrp', nf_ioe: 'NF IOE' },
        howToImprove: 'How to improve',
        rules: {
            thrp: 'Best Thrp (3BV / effective clicks) per level from official, public Standard replays, with no minimum 3BV. Sum adds the three levels, with missing results counting as zero. The original four rankings favor earlier uploads or completion. Expert NF is independent: rank by Thrp below 1, then by the number of perfect games at 1. Games with the same 3BV count separately; this result is excluded from Sum.',
            nf_ioe: 'Official, public Standard NF replays, with no minimum 3BV. Best IOE (3BV / actual clicks) per level; at 1, lower time wins. Sum adds all three levels, with missing results counting as zero. At 3, only Expert time breaks ties. Parentheses show the comparison time in seconds.',
        },
        improve: {
            thrp: 'Upload your own completed Standard replays, bind their identifiers and have them approved. Use fewer effective clicks for the same 3BV, or upload a higher Thrp. After reaching Expert NF Thrp=1, upload more perfect NF games to improve that ranking. Hidden tournament replays count after they are revealed.',
            nf_ioe: 'Upload your own completed Standard NF replays, bind their identifiers and have them approved. Use fewer actual clicks for the same 3BV to improve IOE. After reaching 1, upload a faster perfect replay. Once all three levels are perfect, a faster Expert improves the Sum ranking. Hidden tournament replays count after being revealed.',
        },
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

.efficiency-selector {
    width: 12rem;
    max-width: 100%;
}

.efficiency-color-icon {
    background: linear-gradient(135deg, #e5484d 15%, #c99700 35%, #16a34a 60%, #3b82f6 85%);
    background-clip: text;
    color: transparent;
}
</style>
