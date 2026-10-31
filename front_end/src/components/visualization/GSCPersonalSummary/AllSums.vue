<template>
    <span style="flex: 1" />
    <ElStatistic class="stathead" :title="`${t('score.sum')} ${t('prop.time')}`" :value="roundedSumTime" :precision="3" />
    <ElStatistic class="stathead" :title="`${t('score.sum')} ${t('prop.bvs')}`" :value="roundedSumBvs" :precision="3" />
    <ElStatistic class="stathead" :title="`${t('score.sum')} ${t('prop.stnb')}`" :value="roundedSumStnb" :precision="3" />
    <span style="flex: 1" />
</template>

<script setup lang="ts">
import { ElStatistic } from 'element-plus';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({
    sumTime: {
        type: Number,
        required: true,
    },
    sumBvs: {
        type: Number,
        required: true,
    },
    sumStnb: {
        type: Number,
        required: true,
    },
});

const { t } = useI18n();

function round3(value: number): number {
    return Math.round(value * 1000) / 1000;
}

const roundedSumTime = computed(() => round3(props.sumTime));
const roundedSumBvs = computed(() => round3(props.sumBvs));
const roundedSumStnb = computed(() => round3(props.sumStnb));
</script>

<style lang="less" scoped>
.stathead {
    width: 30%;
    min-width: 12em;
    text-align: center;
}
</style>
