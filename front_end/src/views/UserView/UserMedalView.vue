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
import type { MedalItem, PlayerMedals } from '@/services/medalService';
import { medalCaption, medalLevel, medalSeriesLabel, medalStageLabel, refreshPlayerMedals, saveMedalPins, subscribePlayerMedals } from '@/services/medalService';
import { store } from '@/store';
import { MedalSeries } from '@/utils/medal_const';

type MedalCategory = 'ability' | 'novice' | 'practice' | 'contest' | 'contribution' | 'other';
interface MedalSection { series: string; items: MedalItem[] }
interface MedalCategoryGroup { id: MedalCategory; sections: MedalSection[] }

const categoryOrder: MedalCategory[] = ['ability', 'novice', 'practice', 'contest', 'contribution', 'other'];
const levelRank: Record<string, number> = { b: 0, i: 1, e: 2 };
const seriesByCategory: Record<MedalCategory, string[]> = {
    ability: [MedalSeries.BREAKTHROUGH, MedalSeries.SPEED, MedalSeries.MASTERY, MedalSeries.FLAGLESS_BREAKTHROUGH, MedalSeries.FLAGLESS_SPEED, MedalSeries.FLAGLESS_MASTERY, MedalSeries.FLAGLESS_PRECISION, MedalSeries.FLAGGED_PRECISION, MedalSeries.THREE_FLAGLESS_PRECISION, MedalSeries.THREE_FLAGGED_PRECISION],
    novice: [MedalSeries.REGISTERED, MedalSeries.REVIEWED, MedalSeries.LEVELS, MedalSeries.LEVELS_NF, MedalSeries.MODES, MedalSeries.SAOLEI],
    practice: [],
    contest: [],
    contribution: [],
    other: [MedalSeries.SHAREHOLDER],
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

function titleOf(item: MedalItem) {
    return medalCaption(item.series, item.code, item.stage, locale.value).title;
}

function flavorOf(item: MedalItem) {
    return medalCaption(item.series, item.code, item.stage, locale.value).flavor;
}

function meaningOf(item: MedalItem) {
    return medalCaption(item.series, item.code, item.stage, locale.value).meaning;
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
