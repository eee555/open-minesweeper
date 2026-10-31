<template>
    <span ref="root" class="identifier-text" @copy="copyOriginalSelection">
        <template v-if="showInvisibleIdentifiers">
            <template v-for="(part, index) in parts" :key="index">
                <BaseTooltip v-if="part.code" trigger="mouseenter focusin" :show-animation="0" :hide-animation="0">
                    <span class="identifier-escape text-primary" :data-identifier-part="index" tabindex="0" :aria-label="description(part)">{{ part.text }}</span>
                    <template #content>{{ description(part) }}</template>
                </BaseTooltip>
                <span v-else :data-identifier-part="index">{{ part.text }}</span>
            </template>
        </template>
        <template v-else>{{ text }}</template>
    </span>
</template>

<script setup lang="ts">
import { computed, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';

import type { IdentifierTextPart } from './identifierDisplay';
import { identifierTextParts, showInvisibleIdentifiers } from './identifierDisplay';

import BaseTooltip from '@/components/common/BaseTooltip.vue';

const props = defineProps({ text: { type: String, required: true } });
const root = useTemplateRef<HTMLSpanElement>('root');
const parts = computed(() => identifierTextParts(props.text));

function description(part: IdentifierTextPart) {
    return `${t('local.escaped')}: ${part.code} ${part.name || t('local.unnamed')}`;
}

function copyOriginalSelection(event: ClipboardEvent) {
    const element = root.value;
    const selection = element?.ownerDocument.getSelection();
    if (!showInvisibleIdentifiers.value || !element || !event.clipboardData || selection?.rangeCount !== 1) return;
    const selected = selection.getRangeAt(0);
    if (!element.contains(selected.startContainer) || !element.contains(selected.endContainer)) return;
    const fragments: string[] = [];
    for (const node of element.querySelectorAll<HTMLElement>('[data-identifier-part]')) {
        if (!selected.intersectsNode(node)) continue;
        const overlap = node.ownerDocument.createRange();
        overlap.selectNodeContents(node);
        if (selected.compareBoundaryPoints(Range.START_TO_START, overlap) > 0) overlap.setStart(selected.startContainer, selected.startOffset);
        if (selected.compareBoundaryPoints(Range.END_TO_END, overlap) < 0) overlap.setEnd(selected.endContainer, selected.endOffset);
        const text = overlap.toString();
        if (text === '') continue;
        const part = parts.value[Number(node.dataset.identifierPart)];
        fragments.push(part.code ? part.raw : text);
    }
    event.clipboardData.setData('text/plain', fragments.join(''));
    event.preventDefault();
}

const i18nMessages = {
    'zh-cn': { local: { escaped: '转义字符', unnamed: '未命名的不可见字符' } },
    en: { local: { escaped: 'Escaped character', unnamed: 'Unnamed invisible character' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.identifier-text {
    white-space: break-spaces;
    overflow-wrap: anywhere;
    font-family: monospace;
    vertical-align: baseline;
}

.identifier-escape {
    text-decoration: underline dotted;
    text-underline-offset: 0.15em;
    vertical-align: baseline;
}

.identifier-text [data-identifier-part] {
    vertical-align: baseline;
}

.identifier-escape:focus-visible {
    outline: 1px solid currentColor;
    outline-offset: 1px;
}
</style>
