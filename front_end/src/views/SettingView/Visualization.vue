<template>
    <section class="card">
        <h2 class="card-title">
            {{ t('local.visualizationColorScheme') }}
        </h2>
        <div class="layout-stack">
            <div class="coloring-setting">
                <span class="text-regular">{{ t('local.colored') }}</span>
                <ElSwitch v-model="local.colored" :aria-label="t('local.colored')" data-cy="coloring-switch" />
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 2rem; align-items: center">
                <div class="text-regular">
                    {{ t('local.level') }}
                </div>
                <span v-for="level in ['b', 'i', 'e', 'c']" class="text-regular" style="display: flex; gap: 0.5em">
                    <span>{{ t(`level.${level}`) }}</span>
                    <ElColorPicker v-model="colorTheme.level[level]" size="small" />
                </span>
            </div>
            <div v-experimental class="layout-stack" style="gap: 0.5rem;">
                <div class="text-regular">
                    {{ t('local.piecewise') }}
                </div>
                <div class="color-scheme-toolbar">
                    <ElSelect v-model="colorSchemeName">
                        <ElOption label="Bvs / CES / CLS" value="bvs" />
                        <ElOption label="IOE / Thrp / Corr / IOME" value="ioe" />
                        <ElOption label="Beg Time" value="btime" />
                        <ElOption label="Int Time" value="itime" />
                        <ElOption label="Exp Time" value="etime" />
                        <ElOption label="STNB" value="stnb" />
                        <ElOption :label="t('local.grade')" value="grade" />
                    </ElSelect>
                    <BaseButton size="small" :title="t('local.restoreDefault')" @click="restoreDefault">
                        <i class="pi pi-replay" aria-hidden="true" />{{ t('local.restoreDefault') }}
                    </BaseButton>
                </div>
                <ColorSchemeSetting v-model="colorTheme[colorSchemeName]" />
            </div>
        </div>
    </section>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import '@/styles/layout.css';

import { ElColorPicker, ElOption, ElSelect, ElSwitch } from 'element-plus';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { vExperimental } from '@/components/ExperimentalFeature';
import ColorSchemeSetting from '@/components/visualization/ColorSchemeSetting.vue';
import { colorTheme, local } from '@/store';
import { deepMutableCopy } from '@/utils';
import { colorSchemeTemplates } from '@/utils/config';

const colorSchemeName = ref<'bvs' | 'ioe' | 'btime' | 'itime' | 'etime' | 'stnb' | 'grade'>('bvs');

function restoreDefault() {
    colorTheme.value[colorSchemeName.value] = deepMutableCopy(colorSchemeTemplates.ArbiterStatsAuto[colorSchemeName.value]);
}

const i18nMessages = {
    'zh-cn': { local: {
        level: '各级别主色',
        colored: '成绩上色',
        piecewise: '分段色阶',
        grade: '定阶（等价 et 秒数）',
        restoreDefault: '还原默认值',
        visualizationColorScheme: '数据可视化 - 配色方案',
    } },
    en: { local: {
        level: 'Primary Colors for Levels',
        colored: 'Color Results',
        piecewise: 'Piecewise Palette',
        grade: 'Tier (Equivalent et in Seconds)',
        restoreDefault: 'Restore Default',
        visualizationColorScheme: 'Visualization - Color Scheme',
    } },
};

const { t } = useI18n({
    messages: i18nMessages,
});
</script>

<style lang="less" scoped>
.coloring-setting {
    display: flex;
    align-items: center;
    gap: 8px;
}
.color-scheme-toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
}
.color-scheme-toolbar > .el-select {
    width: 240px;
    max-width: 100%;
}
</style>
