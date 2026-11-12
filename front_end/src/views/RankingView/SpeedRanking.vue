<template>
    <section class="speed-ranking">
        <div class="ranking-toolbar">
            <select v-model="selectedRankingName" :aria-label="t('local.rankingName')" class="base-select ranking-selector">
                <option v-for="rankingName in rankingNames" :key="rankingName" :value="rankingName" :title="t(`local.tooltip.${rankingName}`)">
                    {{ t(`local.label.${rankingName}`) }}
                </option>
            </select>
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
                <BaseButton class="square-button" data-cy="ranking-color" :type="local.colored ? 'primary' : 'default'" :aria-label="t('prop.color')" :title="t('prop.color')" :aria-pressed="local.colored" @click="local.colored = !local.colored">
                    <i class="pi pi-palette ranking-color-icon" aria-hidden="true" />
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

import { computed, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterView, useRoute, useRouter } from 'vue-router';
import { Tippy } from 'vue-tippy';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { BaseIconInfo, BaseIconRefresh } from '@/components/common/icon';
import { local } from '@/store/local';

const rankingNames = ['lsf', 'top', 'saolei', 'strict_ng', 'pb', 'collection', 'skill_tt'] as const;
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
        howToImprove: '如何提高成绩',
        improveEligibility: '上传自己的通关录像（部分大榜要求标准模式，详见各榜说明），绑定录像内标识并通过审核。比赛隐藏录像需公开后才计入。',
        improveNF: '普通榜包含 NF 录像；若要提高 NF 项目，录像的有效右键次数必须为 0。',
        improve: {
            lsf: '改善 top 各项前五均值，可提升相应级别、综合软实力及 LSF。上传低用时、高 Bvs 或高 Stnb 录像，初级 3BV ≥ 10、中级 ≥ 30、高级 ≥ 100。已有五条时，新成绩需优于自己的第五条；不足五条时先补齐。',
            top: '上传更低用时、更高 Bvs 或更高 Stnb 的录像，初级 3BV ≥ 10、中级 ≥ 30、高级 ≥ 100。每项独立取最佳五条：已有五条时，新成绩需优于自己的第五条；不足五条时先补齐，不要求五条来自不同 3BV。',
            pb: '上传与所选级别、3BV 完全一致且用时比自己该项 PB 更短的录像。该项尚无成绩时，上传一条合格录像即可建立 PB。',
            collection: '在更多 BV 桶上建立 PB 可提高 BV 数量；频率更高的 BV 对 BV 概率贡献更大；提高各 PB 的 Bvs 可提高 ASB。缺项按 0 计，无需每个 BV 都有成绩。',
            skill_tt: '战力按固定 BV 概率对已有 PB 的 Bvs 加权，缺项按 0 计。新增一个正权重且 Bvs 大于 0 的 PB 总会提高战力；提高已有 PB 的 Bvs 也会提高战力、降低分段典型时。',
            saolei: '上传用时比个人最佳更短，或 Bvs 比个人最佳更高的录像。初级用时要求 3BV ≥ 2，初级 Bvs 要求 ≥ 4，中级 ≥ 30，高级 ≥ 100。三级别单项改善后，对应用时总和或 Bvs 总和会自动更新，无需单独上传合计成绩。',
            strict_ng: '上传强无猜模式、3BV 非空的录像，用时更短或 Bvs 更高即可刷新个人最佳；初级要求 3BV ≥ 2，中级、高级没有 BV 下限。三级别单项改善后，Time 总和或 Bvs 总和自动更新，无需单独上传合计成绩。',
        },
        label: {
            lsf: 'LSF 榜',
            top: 'Top',
            pb: 'PB 榜',
            collection: '收集榜',
            skill_tt: '战力 / 典型时榜',
            saolei: '旧@:{\'website.saolei\'}规则',
            strict_ng: '强无猜',
        },
        tooltip: {
            lsf: '根据 Top 五条成绩与锚点计算三级别、综合软实力及 LSF。',
            top: '标准模式、已审核且非隐藏比赛录像，取每项最佳五条的均值。初级 3BV ≥ 10，中级 ≥ 30，高级 ≥ 100；缺项用时按 999.999 秒补齐，其他指标补 0。',
            pb: '仅限@:{\'mode.std\'}@:{\'prop.mode\'}，按@:{\'prop.level\'}和@:{\'prop.bv\'}分榜',
            collection: '统计个人各级别已有 PB 桶的 BV 数量、BV 概率与 ASB 之和。普通榜包含 NF 录像，NF 榜额外要求有效右键次数为 0。',
            skill_tt: '由个人 PB 与固定 BV 频率表计算战力与典型时；战力越大越好，典型时越小越好。零战力分段的典型时按 999.999 秒补齐。',
            saolei: '仅限@:{\'mode.std\'}@:{\'prop.mode\'}。@:{\'level.b\'}@:{\'prop.time\'}要求@:{\'prop.bv\'} ≥ 2，@:{\'level.b\'}@:{\'prop.bvs\'}要求@:{\'prop.bv\'} ≥ 4，@:{\'level.i\'}要求@:{\'prop.bv\'} ≥ 30，@:{\'level.e\'}要求@:{\'prop.bv\'} ≥ 100',
            strict_ng: '仅限强无猜模式。3BV 必须非空，初级要求 3BV ≥ 2，中级和高级没有下限；普通榜包含 NF 录像。',
        },
    } },
    en: { local: {
        rankingName: 'Ranking',
        howToImprove: 'How to improve',
        improveEligibility: 'Upload your own completed replays (some rankings require Standard mode; see the ranking notes), bind their player identifiers and have them approved. Replays hidden for a tournament count after they are revealed.',
        improveNF: 'Ordinary rankings include NF replays. To improve an NF category, the replay must have zero effective right clicks.',
        improve: {
            lsf: 'Improve your top-five means to raise the corresponding level strength, overall strength and LSF. Upload lower Time, higher Bvs or higher Stnb results with at least 10 3BV on Beginner, 30 on Intermediate or 100 on Expert. With five results, beat your own fifth-best; with fewer, fill the missing slots.',
            top: 'Upload lower Time, higher Bvs or higher Stnb results with at least 10 3BV on Beginner, 30 on Intermediate or 100 on Expert. Each metric selects its own best five: beat your own fifth-best, or fill missing slots if you have fewer than five. Repeated 3BV values are allowed.',
            pb: 'Upload a replay with exactly the selected level and 3BV, and a lower time than your own PB in that category. If you have no result there, one qualifying replay establishes your PB.',
            collection: 'Establish PBs in more BV buckets to raise the BV count; frequent BVs contribute more to BV probability; faster PBs raise ASB. Missing buckets count as zero, so you do not need every BV.',
            skill_tt: 'Skill weights the Bvs of your PBs by fixed BV frequencies, with missing BVs counted as zero. Any new PB with positive weight and positive Bvs raises skill, and improving an existing PB raises skill while lowering segment typical time.',
            saolei: 'Upload a lower Time or higher Bvs than your personal best. Minimum 3BV: Beginner Time 2, Beginner Bvs 4, Intermediate 30, Expert 100. Improving a level record automatically updates its Time or Bvs sum; no separate total-score replay is needed.',
            strict_ng: 'Upload Strict No Guessing replays with a non-null 3BV and a lower Time or higher Bvs than your personal best; Beginner requires 3BV ≥ 2 while Intermediate and Expert have no lower bound. Improving a level record automatically updates its Time or Bvs sum; no separate total-score replay is needed.',
        },
        label: {
            lsf: 'LSF',
            top: 'Top',
            pb: 'PB',
            collection: 'Collection',
            skill_tt: 'Skill / Typical Time',
            saolei: 'Legacy @:website.saolei Rule',
            strict_ng: 'Strict NG',
        },
        tooltip: {
            lsf: 'Level strength, overall strength and LSF calculated from the top five records and anchors.',
            top: 'Mean of the best five official, public Standard replays. Minimum 3BV: Beginner 10, Intermediate 30, Expert 100. Missing times count as 999.999 seconds; other missing values count as zero.',
            pb: 'Standard mode, grouped by level and 3BV. NF additionally requires zero effective right clicks.',
            collection: 'BV count, BV probability and ASB summed over the PBs you own at each level. The ordinary category includes NF replays; NF additionally requires zero effective right clicks.',
            skill_tt: 'Skill and Typical Time computed from your PBs and fixed BV frequencies. Higher skill is better; lower typical time is better. Zero-skill segments use 999.999 seconds.',
            saolei: '@:mode.std mode only. @:level.b @:prop.time requires @:prop.bv ≥ 2. @:level.b @:prop.bvs requires @:prop.bv ≥ 4. @:level.i requires @:prop.bv ≥ 30. @:level.e requires @:prop.bv ≥ 100.',
            strict_ng: 'Strict No Guessing mode only. 3BV must be present and at least 2 for Beginner; Intermediate and Expert have no lower bound. The ordinary ranking includes NF replays.',
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
