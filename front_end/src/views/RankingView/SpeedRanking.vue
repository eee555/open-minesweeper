<template>
    <section class="speed-ranking">
        <div class="ranking-toolbar">
            <ElSelect v-model="selectedRankingName" :aria-label="t('local.rankingName')" class="ranking-selector">
                <ElOption v-for="rankingName in rankingNames" :key="rankingName" :label="t(`local.label.${rankingName}`)" :value="rankingName" :title="t(`local.tooltip.${rankingName}`)" />
            </ElSelect>
            <div class="ranking-help">
                <Tippy>
                    <BaseIconInfo />
                    <template #content>
                        <div class="card card-small">
                            {{ t(`local.tooltip.${selectedRankingName}`) }}
                        </div>
                    </template>
                </Tippy>
                <Tippy :max-width="400" trigger="mouseenter focusin click">
                    <BaseTextButton data-cy="ranking-improve" type="primary" underline="hover">
                        {{ t('local.howToImprove') }}
                    </BaseTextButton>
                    <template #content>
                        <div class="card card-small ranking-improve-content" data-cy="ranking-improve-content">
                            <p>{{ t('local.improveEligibility') }}</p>
                            <p>{{ t(`local.improve.${selectedRankingName}`) }}</p>
                            <p>{{ t('local.improveNF') }}</p>
                        </div>
                    </template>
                </Tippy>
            </div>
            <div class="ranking-actions">
                <BaseButton class="square-button" data-cy="ranking-color" :type="local.colored ? 'primary' : 'default'" :aria-label="t('local.color')" :title="t('local.color')" :aria-pressed="local.colored" @click="local.colored = !local.colored">
                    <i class="pi pi-palette ranking-color-icon" aria-hidden="true" />
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

import { ElOption, ElSelect } from 'element-plus';
import { computed, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterView, useRoute, useRouter } from 'vue-router';
import { Tippy } from 'vue-tippy';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { BaseIconInfo, BaseIconRefresh } from '@/components/common/icon';
import { local } from '@/store/local';

const rankingNames = ['lsf', 'top', 'saolei', 'pb'] as const;
const route = useRoute();
const router = useRouter();
const ranking = useTemplateRef<{ refresh: () => void | Promise<void>; loading: boolean }>('ranking');
const selectedRankingName = computed<typeof rankingNames[number]>({
    get: () => rankingNames.find((name) => route.name === `ranking_speed_${name}`) ?? 'lsf',
    set: (name) => {
        void router.push({ name: `ranking_speed_${name}` });
    },
});

const i18nMessages = {
    'zh-cn': { local: {
        rankingName: '大榜',
        color: '颜色',
        howToImprove: '如何提高成绩',
        improveEligibility: '上传自己的标准模式通关录像，绑定录像内标识并通过审核。比赛隐藏录像需公开后才计入。',
        improveNF: '普通榜包含 NF 录像；若要提高 NF 项目，录像的有效右键次数必须为 0。',
        improve: {
            lsf: '改善 top 各项前五均值，可提升相应级别、综合软实力及 LSF。上传低用时、高 Bvs 或高 Stnb 录像，初级 3BV ≥ 10、中级 ≥ 30、高级 ≥ 100。已有五条时，新成绩需优于自己的第五条；不足五条时先补齐。',
            top: '上传更低用时、更高 Bvs 或更高 Stnb 的录像，初级 3BV ≥ 10、中级 ≥ 30、高级 ≥ 100。每项独立取最佳五条：已有五条时，新成绩需优于自己的第五条；不足五条时先补齐，不要求五条来自不同 3BV。',
            pb: '上传与所选级别、3BV 完全一致且用时比自己该项 PB 更短的录像。该项尚无成绩时，上传一条合格录像即可建立 PB。',
            saolei: '上传用时比个人最佳更短，或 Bvs 比个人最佳更高的录像。初级用时要求 3BV ≥ 2，初级 Bvs 要求 ≥ 4，中级 ≥ 30，高级 ≥ 100。三级别单项改善后，对应用时总和或 Bvs 总和会自动更新，无需单独上传合计成绩。',
        },
        label: {
            lsf: 'LSF 榜',
            top: 'Top',
            pb: 'PB 榜',
            saolei: '旧@:{\'common.website.saolei\'}规则',
        },
        tooltip: {
            lsf: '根据 Top 五条成绩与锚点计算三级别、综合软实力及 LSF。',
            top: '标准模式、已审核且非隐藏比赛录像，取每项最佳五条的均值。初级 3BV ≥ 10，中级 ≥ 30，高级 ≥ 100；缺项用时按 999.999 秒补齐，其他指标补 0。',
            pb: '仅限@:{\'common.mode.std\'}@:{\'common.prop.mode\'}，按@:{\'common.prop.level\'}和@:{\'common.prop.bv\'}分榜',
            saolei: '仅限@:{\'common.mode.std\'}@:{\'common.prop.mode\'}。@:{\'common.level.b\'}@:{\'common.prop.time\'}要求@:{\'common.prop.bv\'} ≥ 2，@:{\'common.level.b\'}@:{\'common.prop.bvs\'}要求@:{\'common.prop.bv\'} ≥ 4，@:{\'common.level.i\'}要求@:{\'common.prop.bv\'} ≥ 30，@:{\'common.level.e\'}要求@:{\'common.prop.bv\'} ≥ 100',
        },
    } },
    en: { local: {
        rankingName: 'Ranking',
        color: 'Color',
        howToImprove: 'How to improve',
        improveEligibility: 'Upload your own completed Standard-mode replays, bind their player identifiers and have them approved. Replays hidden for a tournament count after they are revealed.',
        improveNF: 'Ordinary rankings include NF replays. To improve an NF category, the replay must have zero effective right clicks.',
        improve: {
            lsf: 'Improve your top-five means to raise the corresponding level strength, overall strength and LSF. Upload lower Time, higher Bvs or higher Stnb results with at least 10 3BV on Beginner, 30 on Intermediate or 100 on Expert. With five results, beat your own fifth-best; with fewer, fill the missing slots.',
            top: 'Upload lower Time, higher Bvs or higher Stnb results with at least 10 3BV on Beginner, 30 on Intermediate or 100 on Expert. Each metric selects its own best five: beat your own fifth-best, or fill missing slots if you have fewer than five. Repeated 3BV values are allowed.',
            pb: 'Upload a replay with exactly the selected level and 3BV, and a lower time than your own PB in that category. If you have no result there, one qualifying replay establishes your PB.',
            saolei: 'Upload a lower Time or higher Bvs than your personal best. Minimum 3BV: Beginner Time 2, Beginner Bvs 4, Intermediate 30, Expert 100. Improving a level record automatically updates its Time or Bvs sum; no separate total-score replay is needed.',
        },
        label: {
            lsf: 'LSF',
            top: 'Top',
            pb: 'PB',
            saolei: 'Legacy @:common.website.saolei Rule',
        },
        tooltip: {
            lsf: 'Level strength, overall strength and LSF calculated from the top five records and anchors.',
            top: 'Mean of the best five official, public Standard replays. Minimum 3BV: Beginner 10, Intermediate 30, Expert 100. Missing times count as 999.999 seconds; other missing values count as zero.',
            pb: 'Standard mode, grouped by level and 3BV. NF additionally requires zero effective right clicks.',
            saolei: '@:common.mode.std mode only. @:common.level.b @:common.prop.time requires @:common.prop.bv ≥ 2. @:common.level.b @:common.prop.bvs requires @:common.prop.bv ≥ 4. @:common.level.i requires @:common.prop.bv ≥ 30. @:common.level.e requires @:common.prop.bv ≥ 100.',
        },
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.speed-ranking {
    min-width: 0;
}

.ranking-toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 1.5rem;
    margin-bottom: 1rem;
}

.ranking-help {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.ranking-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-left: auto;
}

.ranking-color-icon {
    background: linear-gradient(135deg, #e5484d 15%, #c99700 35%, #16a34a 60%, #3b82f6 85%);
    background-clip: text;
    color: transparent;
}

.ranking-improve-content p {
    margin: 0;
}

.ranking-improve-content p + p {
    margin-top: 0.5rem;
}

.ranking-selector {
    width: 12rem;
    max-width: 100%;
}
</style>
