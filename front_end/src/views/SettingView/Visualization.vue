<template>
    <section class="card">
        <h2 class="card-title">
            {{ t('local.visualizationColorScheme') }}
        </h2>
        <div class="layout-stack">
            <label class="coloring-setting switch" data-cy="coloring-switch">
                <span class="text-regular">{{ t('local.colored') }}</span>
                <input v-model="local.colored" class="switch-input" type="checkbox" role="switch">
                <span class="switch-track" aria-hidden="true" />
            </label>
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
                    <select v-model="colorSchemeName" class="base-select color-scheme-select" :aria-label="t('local.piecewise')">
                        <option value="bvs">
                            Bvs / CES / CLS
                        </option>
                        <option value="ioe">
                            IOE / Thrp / Corr / IOME
                        </option>
                        <option value="btime">
                            {{ t('local.begTime') }}
                        </option>
                        <option value="itime">
                            {{ t('local.intTime') }}
                        </option>
                        <option value="etime">
                            {{ t('local.expTime') }}
                        </option>
                        <option value="stnb">
                            STNB
                        </option>
                        <option value="grade">
                            {{ t('local.grade') }}
                        </option>
                    </select>
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
import '@/styles/vendors/element-plus.css';
import '@/styles/cards.css';
import '@/styles/layout.css';

import { ElColorPicker } from 'element-plus';
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
        begTime: '初级用时',
        intTime: '中级用时',
        expTime: '高级用时',
        level: '各级别主色',
        colored: '成绩上色',
        piecewise: '分段色阶',
        grade: '定阶（等价 et 秒数）',
        restoreDefault: '还原默认值',
        visualizationColorScheme: '数据可视化 - 配色方案',
    } },
    en: { local: {
        begTime: 'Beg Time',
        intTime: 'Int Time',
        expTime: 'Exp Time',
        level: 'Primary Colors for Levels',
        colored: 'Color Results',
        piecewise: 'Piecewise Palette',
        grade: 'Tier (Equivalent et in Seconds)',
        restoreDefault: 'Restore Default',
        visualizationColorScheme: 'Visualization - Color Scheme',
    } },
    es: { local: {
        begTime: 'Tiempo en principiante',
        intTime: 'Tiempo en intermedio',
        expTime: 'Tiempo en experto',
        level: 'Colores principales por nivel',
        colored: 'Colorear resultados',
        piecewise: 'Escala de colores por tramos',
        grade: 'Nivel (tiempo experto equivalente en segundos)',
        restoreDefault: 'Restaurar valores predeterminados',
        visualizationColorScheme: 'Visualización - Esquema de colores',
    } },
};

const { t } = useI18n({
    messages: i18nMessages,
});
</script>

<style lang="less" scoped>
.coloring-setting {
    gap: 8px;
}
.color-scheme-toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
}
.color-scheme-select {
    width: 240px;
}
</style>
