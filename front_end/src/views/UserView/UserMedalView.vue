<template>
    <div class="medal-page">
        <p v-if="loading">
            {{ t('local.loading') }}
        </p>
        <template v-else>
            <p class="score">
                {{ t('local.score', { value: score }) }}
            </p>
            <p v-if="summary?.scan_pending" class="scan-pending">
                {{ t('local.scanPending') }}
                <BaseButton @click="refreshPlayerMedals(store.player.id)">
                    {{ t('local.retry') }}
                </BaseButton>
            </p>
            <p v-else-if="categories.length === 0" class="empty">
                {{ t('local.empty') }}
            </p>
            <section v-for="category in categories" :key="category.id" class="category">
                <h2 class="category-title">
                    {{ categoryLabel(category.id) }}
                </h2>
                <section v-for="group in category.sections" :key="group.series" class="series">
                    <h3 v-if="group.series && category.id !== 'ability'" class="series-title">
                        {{ seriesLabel(group.series) }}
                    </h3>
                    <ul class="medal-list">
                        <li v-for="item in group.items" :key="itemKey(item)" class="medal-tile">
                            <BaseTooltip :show-animation="0" :hide-animation="0">
                                <div
                                    class="medal-face" :class="{ 'is-pinned': isSelected(item.grant_id), 'is-pickable': canPick(item) }"
                                    :role="canEdit ? 'button' : undefined" :tabindex="canEdit ? 0 : undefined"
                                    :aria-pressed="canEdit ? isSelected(item.grant_id) : undefined" :aria-disabled="canEdit && !canPick(item) ? true : undefined"
                                    :aria-label="canEdit ? titleOf(item) : undefined"
                                    @click="onPick(item)" @keydown.enter.prevent="onPick(item)" @keydown.space.prevent="onPick(item)"
                                >
                                    <MedalArt :series="item.series" :code="item.code" :stage="item.stage" :size="72" framed :pinned="isSelected(item.grant_id)" />
                                </div>
                                <template #content>
                                    <div class="tip-title">
                                        {{ titleOf(item) }}
                                    </div>
                                    <div v-for="(line, index) in detailLines(item)" :key="index" class="tip-line" :class="{ 'is-flavor': line.flavor }">
                                        {{ line.text }}
                                    </div>
                                </template>
                            </BaseTooltip>
                        </li>
                    </ul>
                </section>
            </section>
            <BaseButton v-if="canEdit && categories.length" class="save" type="primary" :disabled="saving" @click="save">
                {{ t('local.save') }}
            </BaseButton>
            <p v-if="message" class="message">
                {{ message }}
            </p>
        </template>
    </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onDeactivated, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import MedalArt from './MedalArt.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTooltip from '@/components/common/BaseTooltip.vue';
import en from '@/i18n/locales/en';
import zhCn from '@/i18n/locales/zh-cn';
import type { MedalItem, PlayerMedals } from '@/services/medalService';
import { medalLevel, medalSeriesLabel, medalStageLabel, refreshPlayerMedals, saveMedalPins, subscribePlayerMedals } from '@/services/medalService';
import { store } from '@/store';

type MedalCategory = 'ability' | 'novice' | 'practice' | 'contest' | 'contribution' | 'other';
interface MedalSection { series: string; items: MedalItem[] }
interface MedalCategoryGroup { id: MedalCategory; sections: MedalSection[] }

const categoryOrder: MedalCategory[] = ['ability', 'novice', 'practice', 'contest', 'contribution', 'other'];
const levelRank: Record<string, number> = { b: 0, i: 1, e: 2 };
const seriesByCategory: Record<MedalCategory, string[]> = {
    ability: ['破境', '神速', '通明', '盲扫破境', '盲扫神速', '盲扫通明', '盲扫·精工', '标旗·精工', '三阶盲扫·精工', '三阶标旗·精工'],
    novice: ['实名在册', '录像过审', '扫雷新秀', '盲扫新秀', '走马观花', '旧迹新篇'],
    practice: [],
    contest: [],
    contribution: [],
    other: ['原始股东'],
};

const summary = ref<PlayerMedals | null>(null);
const selected = ref<number[]>([]);
const loading = ref(false);
const saving = ref(false);
const message = ref('');

function byLevel(items: MedalItem[]) {
    return [...items].sort((left, right) => (levelRank[medalLevel(left.code)] ?? 3) - (levelRank[medalLevel(right.code)] ?? 3));
}

function sameIds(left: number[], right: number[]) {
    return left.length === right.length && left.every((id, index) => id === right[index]);
}

const categories = computed(() => {
    const earned = new Map<string, MedalItem[]>();
    for (const group of summary.value?.series ?? []) {
        const items = group.items.filter((item) => item.grant_id !== null);
        if (items.length) earned.set(group.series, items);
    }
    return categoryOrder.flatMap((id): MedalCategoryGroup[] => {
        const named = seriesByCategory[id].filter((series) => earned.has(series));
        if (id === 'novice') {
            const items = named.flatMap((series) => earned.get(series) ?? []);
            return items.length ? [{ id, sections: [{ series: '', items }] }] : [];
        }
        const extra = id === 'other' ? [...earned.keys()].filter((series) => !named.includes(series) && categoryOrder.every((category) => !seriesByCategory[category].includes(series))) : [];
        const sections = [...named, ...extra].map((series) => ({ series, items: id === 'ability' ? byLevel(earned.get(series) ?? []) : earned.get(series) ?? [] }));
        return sections.length ? [{ id, sections }] : [];
    });
});
const score = computed(() => summary.value?.score ?? 0);
const canEdit = computed(() => store.isSelf);

function categoryLabel(id: MedalCategory) {
    if (id === 'ability') return t('local.category.ability');
    if (id === 'novice') return t('local.category.novice');
    if (id === 'practice') return t('local.category.practice');
    if (id === 'contest') return t('local.category.contest');
    if (id === 'contribution') return t('local.category.contribution');
    return t('local.category.other');
}

function itemKey(item: MedalItem) {
    return `${item.code}:${item.scope_key}:${item.grant_id ?? 'locked'}`;
}

function seriesLabel(name: string) {
    return medalSeriesLabel(name, locale.value);
}

function levelWord(names: { b: string; i: string; e: string }, code: string) {
    const level = medalLevel(code);
    if (level !== 'b' && level !== 'i' && level !== 'e') return '';
    return names[level];
}

function titleOf(item: MedalItem) {
    const chinese = locale.value.startsWith('zh');
    const seriesName = medalSeriesLabel(item.series, locale.value);
    const stage = medalStageLabel(item.series, item.stage);
    if (!stage) return seriesName;
    const level = levelWord(chinese ? zhCn.common.level : en.common.level, item.code);
    if (item.series.startsWith('三阶') || !level) return chinese ? `${seriesName}·${stage}` : `${seriesName} · ${stage}`;
    if (!chinese) return `${level} ${seriesName} · ${stage}`;
    return `${level}${seriesName}·${stage}`;
}

function plainStage(item: MedalItem) {
    if (item.stage == null) return '';
    if (item.series === '破境' || item.series === '盲扫破境') return String(item.stage / 1000);
    return medalStageLabel(item.series, item.stage) || String(item.stage);
}

function flavorOf(item: MedalItem) {
    switch (item.series) {
        case '实名在册': return t('local.flavor.registered');
        case '录像过审': return t('local.flavor.reviewed');
        case '扫雷新秀': return t('local.flavor.levels');
        case '盲扫新秀': return t('local.flavor.levelsNf');
        case '走马观花': return t('local.flavor.modes');
        case '旧迹新篇': return t('local.flavor.saolei');
        case '原始股东': return t('local.flavor.shareholder');
        default: return '';
    }
}

function meaningOf(item: MedalItem) {
    const level = levelWord(locale.value.startsWith('zh') ? zhCn.common.level : en.common.level, item.code);
    const value = plainStage(item);
    switch (item.series) {
        case '破境': return t('local.meaning.time', { level, value });
        case '盲扫破境': return t('local.meaning.timeNf', { level, value });
        case '神速': return t('local.meaning.speed', { level, value });
        case '盲扫神速': return t('local.meaning.speedNf', { level, value });
        case '通明': return t('local.meaning.mastery', { level, value });
        case '盲扫通明': return t('local.meaning.masteryNf', { level, value });
        case '盲扫·精工': return t('local.meaning.precisionNf', { level, value });
        case '标旗·精工': return t('local.meaning.precisionFl', { level, value });
        case '三阶盲扫·精工': return t('local.meaning.threeNf', { value });
        case '三阶标旗·精工': return t('local.meaning.threeFl', { value });
        case '实名在册': return t('local.meaning.registered');
        case '录像过审': return t('local.meaning.reviewed');
        case '扫雷新秀': return t('local.meaning.levels');
        case '盲扫新秀': return t('local.meaning.levelsNf');
        case '走马观花': return t('local.meaning.modes');
        case '旧迹新篇': return t('local.meaning.saolei');
        case '原始股东': return t('local.meaning.shareholder', { value });
        default: return '';
    }
}

function detailLines(item: MedalItem) {
    const lines: { text: string; flavor: boolean }[] = [];
    const flavor = flavorOf(item);
    const meaning = meaningOf(item);
    if (flavor) lines.push({ text: flavor, flavor: true });
    if (meaning) lines.push({ text: meaning, flavor: false });
    if (item.annotation) lines.push({ text: item.annotation, flavor: false });
    if (item.stage_count > 1 && item.next_threshold != null) lines.push({ text: t('local.next', { value: medalStageLabel(item.series, item.next_threshold) }), flavor: false });
    if (item.score > 0) lines.push({ text: t('local.points', { value: item.score }), flavor: false });
    return lines;
}

function isSelected(grantId: number | null) {
    return grantId !== null && selected.value.includes(grantId);
}

function pinLimit() {
    return summary.value?.max_pins ?? 0;
}

function canPick(item: MedalItem) {
    return canEdit.value && item.grant_id !== null && (isSelected(item.grant_id) || selected.value.length < pinLimit());
}

function onPick(item: MedalItem) {
    if (!canPick(item) || item.grant_id === null) return;
    toggle(item.grant_id, !isSelected(item.grant_id));
}

function toggle(grantId: number, checked: boolean) {
    const next = selected.value.filter((id) => id !== grantId);
    if (checked && next.length < pinLimit()) next.push(grantId);
    selected.value = next;
}

const loadedFor = ref(0);

async function save() {
    const playerId = store.player.id;
    saving.value = true;
    message.value = '';
    try {
        await saveMedalPins(selected.value, playerId);
    } catch {
        if (viewing.value && store.player.id === playerId) message.value = t('local.saveFailed');
    } finally {
        saving.value = false;
    }
}

const viewing = ref(true);
onActivated(() => {
    viewing.value = true;
});
onDeactivated(() => {
    viewing.value = false;
});
watch(() => [store.player.id, viewing.value], (_, __, onCleanup) => {
    const playerId = store.player.id;
    message.value = '';
    if (loadedFor.value !== playerId) {
        summary.value = null;
        selected.value = [];
        loadedFor.value = 0;
    }
    loading.value = false;
    if (!viewing.value || !playerId) return;
    loading.value = summary.value === null;
    onCleanup(subscribePlayerMedals(playerId, (data) => {
        const dirty = summary.value !== null && !sameIds(selected.value, summary.value.pin_ids);
        summary.value = data;
        loadedFor.value = playerId;
        loading.value = false;
        message.value = '';
        if (!dirty) selected.value = data.pin_ids.slice();
        else {
            const owned = new Set(data.series.flatMap((group) => group.items.flatMap((item) => (item.grant_id === null ? [] : [item.grant_id]))));
            selected.value = selected.value.filter((id) => owned.has(id));
        }
    }, () => {
        loading.value = false;
        message.value = t('local.loadFailed');
    }));
}, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: {
        loading: '加载中',
        empty: '还没有勋章',
        scanPending: '历史勋章正在补发。若未自动更新，请稍后重试。',
        retry: '重新加载',
        score: '总分{value}',
        points: '分数{value}',
        next: '下一档{value}',
        save: '保存佩戴',
        saveFailed: '佩戴没有保存',
        loadFailed: '勋章没有加载出来',
        category: { ability: '能力称号', novice: '新手称号', practice: '历练称号', contest: '比赛称号', contribution: '贡献称号', other: '其他称号' },
        meaning: {
            time: '{level}最快时间达到{value}秒。',
            timeNf: '{level}盲扫最快时间达到{value}秒。',
            speed: '{level}最高3BV/s达到{value}。',
            speedNf: '{level}盲扫最高3BV/s达到{value}。',
            mastery: '{level}最高STNB达到{value}。',
            masteryNf: '{level}盲扫最高STNB达到{value}。',
            precisionNf: '{level}盲扫最高thrp达到{value}。',
            precisionFl: '{level}标雷最高thrp达到{value}。',
            threeNf: '三级别盲扫thrp达到{value}。',
            threeFl: '三级别thrp达到{value}。',
            registered: '已实名。',
            reviewed: '至少一条录像过审。',
            levels: '初级、中级、高级各有过审录像。',
            levelsNf: '三个级别各有过审盲扫。',
            modes: '每种开放模式都有过审录像。',
            saolei: '导入过一条扫雷网录像。',
            shareholder: '名下最小录像编号低于{value}。',
        },
        flavor: {
            registered: '你的名字是...',
            reviewed: 'Talk is cheap, show me the video.',
            levels: '欢迎来到，开源扫雷网。',
            levelsNf: '我不标旗啦！JOJO！',
            modes: '我全都要！',
            saolei: '新时代仍有载我的船。',
            shareholder: '老资历',
        },
    } },
    en: { local: {
        loading: 'Loading',
        empty: 'No medals yet',
        scanPending: 'Historical medals are being awarded. If they do not update automatically, try again shortly.',
        retry: 'Reload',
        score: 'Score {value}',
        points: 'Points {value}',
        next: 'Next {value}',
        save: 'Save pins',
        saveFailed: 'Could not save pins',
        loadFailed: 'Could not load medals',
        category: { ability: 'Ability', novice: 'Novice', practice: 'Practice', contest: 'Competition', contribution: 'Contribution', other: 'Other' },
        meaning: {
            time: '{level} best time reached {value}s.',
            timeNf: '{level} no-flag best time reached {value}s.',
            speed: '{level} best 3BV/s reached {value}.',
            speedNf: '{level} no-flag best 3BV/s reached {value}.',
            mastery: '{level} best STNB reached {value}.',
            masteryNf: '{level} no-flag best STNB reached {value}.',
            precisionNf: '{level} no-flag best thrp reached {value}.',
            precisionFl: '{level} flagged best thrp reached {value}.',
            threeNf: 'no-flag thrp on all 3 levels reached {value}.',
            threeFl: 'Thrp on all 3 levels reached {value}.',
            registered: 'Real-named, not anonymous.',
            reviewed: 'At least one approved replay.',
            levels: 'Approved replay on each level.',
            levelsNf: 'Approved no-flag replay on each level.',
            modes: 'Approved replay in every open mode.',
            saolei: 'Imported a Saolei.net replay.',
            shareholder: 'Smallest replay id under {value}.',
        },
        flavor: {
            registered: 'Your name is...',
            reviewed: 'Talk is cheap, show me the video.',
            levels: 'Welcome to Open Minesweeper.',
            levelsNf: 'No flags for me! JOJO!',
            modes: 'I want them all!',
            saolei: 'A boat still carries me in this new age.',
            shareholder: 'Old hand.',
        },
    } },
};
const { t } = useI18n({ messages: i18nMessages });
const { locale } = useI18n({ useScope: 'global' });
</script>

<style scoped lang="less">
.medal-page {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.score,
.empty,
.message {
    margin: 0;
    color: var(--ui-text-color-regular);
}

.category {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.category-title {
    margin: 0;
    color: var(--ui-text-color-primary);
    font-size: var(--ui-font-size-large);
}

.series-title {
    margin: 0 0 4px;
    color: var(--ui-text-color-regular);
    font-size: var(--ui-font-size-base);
    font-weight: 600;
}

.medal-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 0;
    padding: 0;
    list-style: none;
}

.medal-face {
    width: 72px;
    height: 72px;
}

.medal-face.is-pickable {
    cursor: pointer;
}

.tip-title {
    color: var(--ui-text-color-primary);
}

.tip-line {
    color: var(--ui-text-color-secondary);
    font-size: var(--ui-font-size-small);
}

.tip-line.is-flavor {
    color: var(--ui-text-color-regular);
    font-size: var(--ui-font-size-base);
}

.save {
    align-self: flex-start;
}
</style>
