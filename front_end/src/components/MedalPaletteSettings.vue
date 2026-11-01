<template>
    <section class="card medal-colors">
        <h2 class="card-title">
            {{ t('local.title') }}
        </h2>
        <p class="text text-small">
            {{ t('local.description') }}
        </p>
        <label :for="`${id}-code`">{{ t('local.definition') }}</label>
        <select :id="`${id}-code`" v-model="selectedCode">
            <option v-for="(appearance, code) in MEDAL_APPEARANCES" :key="code" :value="code">
                {{ definitionLabel(appearance) }}
            </option>
        </select>
        <div class="palette-rows">
            <div v-for="(color, index) in medalPalette.colors" :key="index" class="palette-row">
                <label :for="`${id}-tier-${index}`">{{ t('local.tier', { tier: index + 1 }) }}</label>
                <input :id="`${id}-tier-${index}`" type="color" :value="color" :aria-label="t('local.tier', { tier: index + 1 })" @input="setTier(index, ($event.target as HTMLInputElement).value)">
                <input class="hex" type="text" :value="color" maxlength="7" :aria-label="t('local.hex', { tier: index + 1 })" spellcheck="false" @input="tierInput(index, ($event.target as HTMLInputElement).value)" @change="setTier(index, ($event.target as HTMLInputElement).value)">
                <BaseButton size="small" @click="setTier(index, DEFAULT_MEDAL_COLORS[index])">
                    {{ t('local.resetOne') }}
                </BaseButton>
                <MedalArt :series="selected.series" :code="selectedCode" :stage="selected.groups[index][0]" :size="48" />
            </div>
        </div>
        <div class="actions">
            <BaseButton size="small" @click="resetMedalPalette()">
                {{ t('local.reset') }}
            </BaseButton>
            <BaseButton size="small" @click="exportConfig">
                {{ t('local.export') }}
            </BaseButton>
            <BaseButton size="small" @click="fileInput?.click()">
                {{ t('local.import') }}
            </BaseButton>
            <input ref="fileInput" type="file" accept=".json,application/json" hidden @change="importConfig">
        </div>
        <p class="text text-small" role="status">
            {{ t(`local.status.${medalPaletteStorageStatus}`) }}
        </p>
        <p v-if="error" class="error text text-small" role="alert">
            {{ error }}
        </p>
        <details>
            <summary>{{ t('local.advanced') }}</summary>
            <div class="override-rows">
                <div v-for="row in stages" :key="row.stage" class="override-row">
                    <span>{{ medalStageLabel(selected.series, row.stage) }} · {{ t('local.tier', { tier: row.tier }) }}</span>
                    <input type="color" :value="stageColor(row.stage, row.tier)" :aria-label="t('local.override', { stage: medalStageLabel(selected.series, row.stage) })" @input="setStage(row.stage, ($event.target as HTMLInputElement).value)">
                    <input class="hex" type="text" :value="stageColor(row.stage, row.tier)" maxlength="7" :aria-label="t('local.override', { stage: medalStageLabel(selected.series, row.stage) })" @input="stageInput(row.stage, ($event.target as HTMLInputElement).value)" @change="setStage(row.stage, ($event.target as HTMLInputElement).value)">
                    <BaseButton size="small" :disabled="!hasOverride(row.stage)" @click="clearStage(row.stage)">
                        {{ t('local.followTier') }}
                    </BaseButton>
                </div>
            </div>
        </details>
    </section>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import '@/styles/text.css';
import { computed, ref, useId, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { MEDAL_APPEARANCES } from '@/services/medalAppearance';
import type { MedalAppearance } from '@/services/medalAppearance';
import { DEFAULT_MEDAL_COLORS, MAX_MEDAL_PALETTE_JSON_LENGTH, medalPaletteColor, normalizeMedalColor, parseMedalPalette } from '@/services/medalPalette';
import { medalPalette, medalPaletteStorageStatus, resetMedalPalette, updateMedalPalette } from '@/services/medalPaletteStore';
import { medalSeriesLabel, medalStageLabel } from '@/services/medalService';
import MedalArt from '@/views/UserView/MedalArt.vue';

const id = useId();
const error = ref('');
const selectedCode = ref('ability.time.b');
const selected = computed(() => MEDAL_APPEARANCES[selectedCode.value]);
const stages = computed(() => selected.value.groups.flatMap((group, index) => group.map((stage) => ({ stage, tier: index + 1 }))));
const fileInput = useTemplateRef<HTMLInputElement>('fileInput');

function definitionLabel(appearance: MedalAppearance) {
    return `${medalSeriesLabel(appearance.series, locale.value)} · ${t('local.difficulty.' + appearance.difficulty)}`;
}
function tierInput(index: number, color: string) {
    if ((/^#[\da-f]{6}$/i).test(color)) setTier(index, color);
}
function stageInput(stage: number, color: string) {
    if ((/^#[\da-f]{6}$/i).test(color)) setStage(stage, color);
}
function setTier(index: number, color: string) {
    try {
        const next = parseMedalPalette(JSON.stringify(medalPalette.value));
        next.colors[index] = normalizeMedalColor(color);
        updateMedalPalette(next); error.value = '';
    } catch {
        error.value = t('local.invalidColor');
    }
}
function stageColor(stage: number, tier: number) {
    return medalPaletteColor(medalPalette.value, tier, selectedCode.value, stage) ?? '#7A7E87';
}
function hasOverride(stage: number) {
    return Object.hasOwn(medalPalette.value.stages[selectedCode.value] ?? {}, String(stage));
}
function setStage(stage: number, color: string) {
    try {
        const next = parseMedalPalette(JSON.stringify(medalPalette.value));
        next.stages[selectedCode.value] ??= {};
        next.stages[selectedCode.value][String(stage)] = normalizeMedalColor(color);
        updateMedalPalette(next); error.value = '';
    } catch {
        error.value = t('local.invalidColor');
    }
}
function clearStage(stage: number) {
    const next = parseMedalPalette(JSON.stringify(medalPalette.value));
    const remaining = Object.fromEntries(Object.entries(next.stages[selectedCode.value] ?? {}).filter(([key]) => key !== String(stage)));
    next.stages = Object.fromEntries(Object.entries(next.stages).filter(([key]) => key !== selectedCode.value));
    if (Object.keys(remaining).length > 0) next.stages[selectedCode.value] = remaining;
    updateMedalPalette(next); error.value = '';
}
function exportConfig() {
    const address = URL.createObjectURL(new Blob([JSON.stringify(medalPalette.value, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = address; anchor.download = 'medal-palette.json'; anchor.click();
    setTimeout(() => {
        URL.revokeObjectURL(address);
    }, 10000);
}
async function importConfig(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0]; if (!file) return;
    try {
        if (file.size > MAX_MEDAL_PALETTE_JSON_LENGTH) throw new Error('size');
        updateMedalPalette(parseMedalPalette(await file.text())); error.value = '';
    } catch {
        error.value = t('local.invalidImport');
    } finally {
        input.value = '';
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        title: '勋章配色',
        description: '默认采用柔和金属。只改变你看到的颜色，不改变成绩、门槛或其他人的设置。星数表示难度，颜色表示成绩档次。',
        tier: '色档 {tier}',
        hex: '色档 {tier} 的 HEX 色值',
        resetOne: '默认',
        reset: '恢复全部默认',
        export: '导出 JSON',
        import: '导入 JSON',
        advanced: '单个门槛设色',
        definition: '称号与难度',
        override: '{stage} 的颜色',
        followTier: '跟随色档',
        invalidColor: '请输入 #RRGGBB 格式的颜色。',
        invalidImport: '导入失败。请使用不超过 64 KiB 的有效勋章配色 JSON。',
        difficulty: { b: '初级', i: '中级', e: '高级' },
        status: { default: '当前为默认配色，修改后自动保存。', saved: '个人配色已保存在此浏览器。', unavailable: '当前配色已生效，但浏览器无法保存；可导出 JSON 备份。', invalid: '原配色格式无效，已显示默认配色。' },
    } },
    en: { local: {
        title: 'Medal colors',
        description: 'Soft metal is the default. Changes affect your view only, not scores, thresholds or other users. Stars show difficulty; colors show score tiers.',
        tier: 'Tier {tier}',
        hex: 'HEX color for tier {tier}',
        resetOne: 'Default',
        reset: 'Reset all colors',
        export: 'Export JSON',
        import: 'Import JSON',
        advanced: 'Individual threshold colors',
        definition: 'Title and difficulty',
        override: 'Color for {stage}',
        followTier: 'Use tier color',
        invalidColor: 'Enter a color in #RRGGBB format.',
        invalidImport: 'Import failed. Use valid medal palette JSON no larger than 64 KiB.',
        difficulty: { b: 'Beginner', i: 'Intermediate', e: 'Expert' },
        status: { default: 'Default colors. Changes are saved automatically.', saved: 'Personal colors saved in this browser.', unavailable: 'Colors applied, but browser storage is unavailable. Export JSON to keep a copy.', invalid: 'Saved colors were invalid. Showing defaults.' },
    } },
};
const { t } = useI18n({ messages: i18nMessages });
const { locale } = useI18n({ useScope: 'global' });
</script>

<style scoped>
.medal-colors {
    min-width: 0;
}
.palette-rows, .override-rows {
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.palette-row, .override-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}
.palette-row label {
    min-width: 58px;
}
.override-row > span {
    min-width: 140px;
}
input[type=color] {
    width: 40px;
    height: 28px;
    padding: 2px;
    border: 1px solid var(--ui-border-color);
    background: var(--ui-bg-color);
    cursor: pointer;
}
.hex, select {
    box-sizing: border-box;
    padding: 4px 6px;
    border: 1px solid var(--ui-border-color);
    background: var(--ui-bg-color);
    color: var(--ui-text-color-regular);
    font: inherit;
}
.hex {
    width: 100px;
}
select {
    max-width: 100%;
    margin: 8px;
}
.actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 10px;
}
.error {
    color: var(--ui-color-danger);
}
summary {
    cursor: pointer;
    color: var(--ui-text-color-primary);
}
:focus-visible {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: 2px;
}
</style>
