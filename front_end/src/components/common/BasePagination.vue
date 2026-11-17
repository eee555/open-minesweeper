<template>
    <nav ref="navRef" class="base-pagination" :aria-label="t('local.pagination')" data-cy="pagination">
        <div class="base-pagination__group" data-cy="nav-buttons">
            <BaseButton class="square-button" size="small" :disabled="disabled || !canGoBack" :aria-label="t('local.prev')" data-cy="prev" @click="goTo(previousStartValue)">
                <template #icon>
                    <i class="pi pi-angle-left" aria-hidden="true" />
                </template>
            </BaseButton>
            <BaseButton class="square-button" size="small" :disabled="disabled || !canGoForward" :aria-label="t('local.next')" data-cy="next" @click="goTo(nextStartValue)">
                <template #icon>
                    <i class="pi pi-angle-right" aria-hidden="true" />
                </template>
            </BaseButton>
            <template v-for="(item, index) in items" :key="index">
                <span v-if="item.type === 'ellipsis'" class="base-pagination__ellipsis" aria-hidden="true">…</span>
                <BaseButton v-else size="small" :type="item.current ? 'primary' : 'default'" :disabled="disabled" :aria-current="item.current ? 'page' : undefined" :aria-label="t('local.range', { start: item.start, end: item.end })" data-cy="segment" @click="goTo(item.start)">
                    {{ item.start }}-{{ item.end }}
                </BaseButton>
            </template>
        </div>
        <div class="base-pagination__group" data-cy="settings">
            <label class="base-pagination__field">
                <span class="text-small">{{ t('local.perPage') }}</span>
                <select class="base-select base-select--small" :value="effectivePageSize" :disabled="disabled" :aria-label="t('local.perPage')" data-cy="page-size" @change="handlePageSizeChange">
                    <option v-if="!pageSizeOptions.includes(effectivePageSize)" :value="effectivePageSize">{{ effectivePageSize }}</option>
                    <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}</option>
                </select>
            </label>
            <label class="base-pagination__field">
                <span class="text-small">{{ t('local.jump') }}</span>
                <input v-model="jumpValue" class="base-pagination__jump" type="text" inputmode="numeric" :disabled="disabled || normalizedTotal === 0" :aria-label="t('local.jumpStartIndex')" data-cy="jump" @keydown.enter.prevent="commitJump" @blur="commitJump">
            </label>
            <span class="base-pagination__report text-secondary text-small" data-cy="report">{{ range.start }}-{{ range.end }} / {{ normalizedTotal }}</span>
        </div>
    </nav>
</template>

<script setup lang="ts">
import '@/styles/pagination.css';
import 'primeicons/primeicons.css';

import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from './BaseButton.vue';
import {
    buildPaginationItems, canGoNext, clampStart, maxSegmentsForWidth,
    nextStart, normalizePageSize, normalizeTotal, previousStart, rangeFor,
} from './pagination';
import type { PaginationRange } from './pagination';

const props = defineProps({
    total: { type: Number, default: 0 },
    pageSizeOptions: { type: Array<number>, default: () => [5, 10, 25, 50, 100] },
    disabled: { type: Boolean, default: false },
});

const emit = defineEmits<{
    change: [range: PaginationRange];
}>();

const currentStart = defineModel<number>('currentStart', { default: 1 });
const pageSize = defineModel<number>('pageSize', { default: 25 });

const normalizedTotal = computed(() => normalizeTotal(props.total));
const effectivePageSize = computed(() => normalizePageSize(pageSize.value));
const effectiveStart = computed(() => clampStart(currentStart.value, normalizedTotal.value));
const range = computed(() => rangeFor(normalizedTotal.value, effectivePageSize.value, effectiveStart.value));
const navRef = useTemplateRef<HTMLElement>('navRef');
const availableWidth = ref(0);
const maxSegments = computed(() => maxSegmentsForWidth(availableWidth.value));
const items = computed(() => buildPaginationItems({
    total: normalizedTotal.value,
    pageSize: effectivePageSize.value,
    currentStart: effectiveStart.value,
    maxSegments: maxSegments.value,
}));
const canGoBack = computed(() => normalizedTotal.value > 0 && effectiveStart.value > 1);
const canGoForward = computed(() => canGoNext(range.value, normalizedTotal.value));
const previousStartValue = computed(() => previousStart(effectiveStart.value, normalizedTotal.value, effectivePageSize.value));
const nextStartValue = computed(() => nextStart(effectiveStart.value, normalizedTotal.value, effectivePageSize.value));

const jumpValue = ref<string>(String(effectiveStart.value));

let observer: ResizeObserver | undefined;
let resizeFrame = 0;

onMounted(() => {
    const nav = navRef.value;
    if (nav === null) return;
    availableWidth.value = nav.clientWidth;
    observer = new ResizeObserver((entries) => {
        const width = entries[0]?.contentRect.width;
        if (width === undefined) return;
        cancelAnimationFrame(resizeFrame);
        resizeFrame = requestAnimationFrame(() => {
            const rounded = Math.round(width);
            if (rounded !== availableWidth.value) availableWidth.value = rounded;
        });
    });
    observer.observe(nav);
});

onBeforeUnmount(() => {
    observer?.disconnect();
    cancelAnimationFrame(resizeFrame);
});

watch([normalizedTotal, effectivePageSize, currentStart], () => {
    if (currentStart.value !== effectiveStart.value) currentStart.value = effectiveStart.value;
    jumpValue.value = String(effectiveStart.value);
}, { immediate: true });

function emitChange(start: number, size: number) {
    emit('change', rangeFor(normalizedTotal.value, size, start));
}

function goTo(target: number) {
    if (props.disabled || normalizedTotal.value === 0) return;
    const next = clampStart(target, normalizedTotal.value);
    if (next === effectiveStart.value) return;
    currentStart.value = next;
    emitChange(next, effectivePageSize.value);
}

function handlePageSizeChange(event: Event) {
    const target = event.target as HTMLSelectElement;
    const next = Number(target.value);
    if (props.disabled || !Number.isInteger(next) || next < 1) return;
    pageSize.value = next;
    currentStart.value = 1;
    emitChange(1, next);
}

function commitJump() {
    if (props.disabled) return;
    const raw = jumpValue.value.trim();
    const parsed = Number(raw);
    const valid = raw !== '' && Number.isInteger(parsed);
    const next = valid ? clampStart(parsed, normalizedTotal.value) : effectiveStart.value;
    jumpValue.value = String(next);
    if (!valid || normalizedTotal.value === 0 || next === effectiveStart.value) return;
    currentStart.value = next;
    emitChange(next, effectivePageSize.value);
}

const i18nMessages = {
    'zh-cn': { local: {
        pagination: '分页',
        prev: '上一页',
        next: '下一页',
        perPage: '每页',
        jump: '跳转',
        jumpStartIndex: '跳转到起始索引',
        range: '第 {start}-{end} 条',
    } },
    en: { local: {
        pagination: 'Pagination',
        prev: 'Previous',
        next: 'Next',
        perPage: 'Per page',
        jump: 'Jump',
        jumpStartIndex: 'Jump to start index',
        range: 'Records {start}-{end}',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
