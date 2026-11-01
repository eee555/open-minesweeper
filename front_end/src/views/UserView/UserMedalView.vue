<template>
    <div class="medal-page">
        <details @toggle="showPalette = ($event.target as HTMLDetailsElement).open">
            <summary>{{ t('local.colors') }}</summary>
            <MedalPaletteSettings v-if="showPalette" />
        </details>
        <p v-if="loading">
            {{ t('local.loading') }}
        </p>
        <template v-else>
            <section v-if="summary" class="pin-editor">
                <div class="toolbar">
                    <strong>{{ editing ? t('local.draft') : t('local.pins') }}</strong>
                    <BaseButton v-if="canEdit && !editing" @click="editing = true">
                        {{ t('local.manage') }}
                    </BaseButton>
                    <template v-if="editing && canEdit">
                        <span>{{ t('local.selected', { count: selected.length, max: pinLimit() }) }}</span>
                        <span v-if="dirty">{{ t('local.unsaved') }}</span>
                        <BaseButton class="save" type="primary" :disabled="saving" @click="save">
                            {{ t('local.save') }}
                        </BaseButton>
                        <BaseButton :disabled="saving" @click="cancelEdit">
                            {{ t('local.cancel') }}
                        </BaseButton>
                    </template>
                </div>
                <ol class="pin-preview">
                    <li v-for="(item, index) in displayedPins" :key="itemKey(item)">
                        <MedalArt :series="item.series" :code="item.code" :stage="item.stage" :size="64" corner-plate />
                        <span>{{ titleOf(item) }}</span>
                        <div v-if="editing && canEdit" class="toolbar">
                            <BaseButton :disabled="saving || index === 0" :aria-label="t('local.earlier')" @click="movePin(index, -1)">
                                ←
                            </BaseButton>
                            <BaseButton :disabled="saving || index === displayedPins.length - 1" :aria-label="t('local.later')" @click="movePin(index, 1)">
                                →
                            </BaseButton>
                            <BaseButton :disabled="saving" @click="onPick(item)">
                                {{ t('local.remove') }}
                            </BaseButton>
                        </div>
                    </li>
                </ol>
                <p v-if="!displayedPins.length">
                    {{ t('local.noPins') }}
                </p>
            </section>
            <div class="filters toolbar" role="group" :aria-label="t('local.all')">
                <BaseButton :type="!earnedOnly ? 'primary' : 'default'" :aria-pressed="!earnedOnly" @click="earnedOnly = false">
                    {{ t('local.all') }} {{ visibleItems.length }}
                </BaseButton>
                <BaseButton :type="earnedOnly ? 'primary' : 'default'" :aria-pressed="earnedOnly" @click="earnedOnly = true">
                    {{ t('local.earned') }} {{ earnedItems.length }}
                </BaseButton>
            </div>
            <p v-if="summary?.scan_pending" class="scan-pending">
                {{ t('local.scanPending') }}
            </p>
            <p v-if="message" role="status" class="message">
                {{ message }}
            </p>
            <BaseButton v-if="loadError || summary?.scan_pending" @click="refreshPlayerMedals(store.player.id)">
                {{ t('local.retry') }}
            </BaseButton>
            <p v-if="!loadError && !summary?.scan_pending && categories.length === 0" class="empty">
                {{ t('local.empty') }}
            </p>
            <section v-for="category in categories" :key="category.id" class="category">
                <h2 class="category-title">
                    {{ categoryLabel(category.id) }}
                </h2>
                <template v-for="group in category.sections" :key="group.series">
                    <MedalRow v-for="item in group.items" :key="itemKey(item)" :item="item" :editing="canEdit && editing" :selected="isSelected(item.grant_id)" :disabled="saving" @pick="onPick(item)" />
                </template>
            </section>
        </template>
    </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onDeactivated, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import MedalArt from './MedalArt.vue';
import MedalRow from './MedalRow.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import MedalPaletteSettings from '@/components/MedalPaletteSettings.vue';
import type { MedalItem, PlayerMedals } from '@/services/medalService';
import { medalDisplayName, medalLevel, refreshPlayerMedals, saveMedalPins, subscribePlayerMedals } from '@/services/medalService';
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
const showPalette = ref(false);
const selected = ref<number[]>([]);
const loading = ref(false);
const saving = ref(false);
const message = ref('');
const loadError = ref(false);
const earnedOnly = ref(false);
const editing = ref(false);
const visibleItems = computed(() => {
    const unique = new Map<string, MedalItem>();
    for (const group of summary.value?.series ?? []) for (const item of group.items) {
        if (!item.hidden || item.grant_id !== null) unique.set(itemKey(item), item);
    }
    return [...unique.values()];
});
const earnedItems = computed(() => visibleItems.value.filter((item) => item.grant_id !== null && item.stage !== null));
const dirty = computed(() => !sameIds(selected.value, summary.value?.pin_ids ?? []));
const displayedPins = computed(() => (editing.value ? selected.value : summary.value?.pin_ids ?? []).flatMap((id) => {
    const item = earnedItems.value.find((entry) => entry.grant_id === id);
    return item ? [item] : [];
}));
function cancelEdit() {
    selected.value = summary.value?.pin_ids.slice() ?? []; editing.value = false; message.value = '';
}
function movePin(index: number, offset: number) {
    const next = selected.value.slice();
    const destination = index + offset;
    if (destination < 0 || destination >= next.length) return;
    [next[index], next[destination]] = [next[destination], next[index]];
    selected.value = next;
}

function byLevel(items: MedalItem[]) {
    return [...items].sort((left, right) => (levelRank[medalLevel(left.code)] ?? 3) - (levelRank[medalLevel(right.code)] ?? 3));
}

function sameIds(left: number[], right: number[]) {
    return left.length === right.length && left.every((id, index) => id === right[index]);
}

const categories = computed(() => {
    const earned = new Map<string, MedalItem[]>();
    for (const group of summary.value?.series ?? []) {
        const items = visibleItems.value.filter((item) => item.series === group.series && (!earnedOnly.value || (item.grant_id !== null && item.stage !== null)));
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
    return JSON.stringify([item.code, item.scope_key]);
}

function titleOf(item: MedalItem) {
    return medalDisplayName(item.series, item.code, item.stage, locale.value);
}

function isSelected(grantId: number | null) {
    return grantId !== null && selected.value.includes(grantId);
}

function pinLimit() {
    return summary.value?.max_pins ?? 0;
}

function canPick(item: MedalItem) {
    return canEdit.value && editing.value && !saving.value && item.grant_id !== null && item.stage !== null && (isSelected(item.grant_id) || selected.value.length < pinLimit());
}

function onPick(item: MedalItem) {
    if (!canPick(item) || item.grant_id === null) {
        message.value = t('local.limit'); return;
    }
    toggle(item.grant_id, !isSelected(item.grant_id));
}

function toggle(grantId: number, checked: boolean) {
    const next = selected.value.filter((id) => id !== grantId);
    if (checked && next.length < pinLimit()) next.push(grantId);
    selected.value = next;
}

const loadedFor = ref(0);

async function save() {
    if (!canEdit.value || !editing.value || saving.value) return;
    const playerId = store.player.id;
    saving.value = true;
    message.value = '';
    try {
        await saveMedalPins(selected.value, playerId);
        if (viewing.value && store.player.id === playerId) {
            editing.value = false; message.value = t('local.saved');
        }
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
        editing.value = false;
        earnedOnly.value = false;
        loadedFor.value = 0;
    }
    loading.value = false;
    loadError.value = false;
    if (!viewing.value || !playerId) return;
    loading.value = summary.value === null;
    onCleanup(subscribePlayerMedals(playerId, (data) => {
        const preserveSelection = editing.value && dirty.value;
        summary.value = data;
        loadedFor.value = playerId;
        loading.value = false;
        loadError.value = false;
        message.value = '';
        if (!preserveSelection) selected.value = data.pin_ids.slice();
        else {
            const owned = new Set(data.series.flatMap((group) => group.items.flatMap((item) => (item.grant_id === null ? [] : [item.grant_id]))));
            selected.value = selected.value.filter((id) => owned.has(id)).slice(0, data.max_pins);
        }
    }, () => {
        loading.value = false;
        loadError.value = true;
        message.value = t('local.loadFailed');
    }));
}, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: {
        all: '全部勋章',
        earned: '已获得勋章',
        manage: '管理佩戴',
        pins: '已保存佩戴',
        draft: '待保存选择',
        cancel: '取消修改',
        unsaved: '有未保存的修改',
        selected: '已选 {count} / {max}',
        remove: '移除',
        earlier: '向前移动',
        later: '向后移动',
        noPins: '尚未佩戴勋章',
        limit: '已达到佩戴上限，请先移除一枚。',
        saved: '佩戴已保存',
        colors: '自定义勋章配色',
        loading: '加载中',
        empty: '还没有勋章',
        scanPending: '历史勋章正在补发。若未自动更新，请稍后重试。',
        retry: '重新加载',
        next: '下一档{value}',
        save: '保存佩戴',
        saveFailed: '佩戴没有保存',
        loadFailed: '勋章没有加载出来',
        category: { ability: '能力称号',
            novice: '新手称号',
            practice: '历练称号',
            contest: '比赛称号',
            contribution: '贡献称号',
            other: '其他称号' },
    } },
    en: { local: {
        all: 'All medals',
        earned: 'Earned medals',
        manage: 'Manage pins',
        pins: 'Saved pins',
        draft: 'Pending selection',
        cancel: 'Cancel changes',
        unsaved: 'Unsaved changes',
        selected: 'Selected {count} / {max}',
        remove: 'Remove',
        earlier: 'Move earlier',
        later: 'Move later',
        noPins: 'No pinned medals',
        limit: 'Pin limit reached. Remove a medal first.',
        saved: 'Pins saved',
        colors: 'Customize medal colors',
        loading: 'Loading',
        empty: 'No medals yet',
        scanPending: 'Historical medals are being awarded. If they do not update automatically, try again shortly.',
        retry: 'Reload',
        next: 'Next {value}',
        save: 'Save pins',
        saveFailed: 'Could not save pins',
        loadFailed: 'Could not load medals',
        category: { ability: 'Ability',
            novice: 'Novice',
            practice: 'Practice',
            contest: 'Competition',
            contribution: 'Contribution',
            other: 'Other' },
    } },
};
const { t } = useI18n({ messages: i18nMessages });
const { locale } = useI18n({ useScope: 'global' });
</script>

<style scoped>
.medal-page {
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-width: 0;
    max-width: 100%;
    color: var(--ui-text-color-primary);
}
.toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
}
.pin-editor {
    padding: 12px;
    background: var(--ui-fill-color-light);
}
.pin-preview {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    list-style: none;
    margin: 12px 0 0;
    padding: 0;
}
.pin-preview li {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    flex: 1 1 120px;
    max-width: 180px;
    overflow-wrap: anywhere;
    text-align: center;
}
.category {
    min-width: 0;
}
.category-title {
    margin: 0;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--ui-border-color);
    font-size: var(--ui-font-size-large);
}
.message, .empty {
    margin: 0;
}
</style>
