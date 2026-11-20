<template>
    <figure class="mermaid-diagram">
        <div v-if="error" class="mermaid-diagram__error">
            {{ error }}
        </div>
        <div
            v-else
            ref="container"
            class="mermaid-diagram__body mermaid-pan-zoom-container"
            :data-mermaid-source="source"
        />
    </figure>
</template>

<script lang="ts">
let mermaidEnhancementsInitialized = false;
let modalTooltipFallbackInitialized = false;
</script>

<script setup lang="ts">
import { useData } from 'vitepress';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import 'mermaid-diagram-pan-zoom/styles/mermaid-enhancements.css';

const props = defineProps({
    encodedSource: {
        type: String,
        required: true,
    },
});

const { isDark, lang } = useData();
const container = ref<HTMLElement>();
const error = ref('');

const source = computed(() => decodeURIComponent(props.encodedSource));

function getTooltipElement() {
    let tooltip = document.querySelector<HTMLElement>('.mermaidTooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.className = 'mermaidTooltip';
        tooltip.style.opacity = '0';
        document.body.appendChild(tooltip);
    }
    return tooltip;
}

function getModalTooltipNode(event: Event) {
    const target = event.target;
    if (!(target instanceof Element)) return null;

    const node = target.closest('g.node[title]');
    if (!(node instanceof SVGGraphicsElement)) return null;
    if (!node.closest('.mermaid-modal-overlay')) return null;

    return node;
}

function initModalTooltipFallback() {
    if (modalTooltipFallbackInitialized) return;

    document.addEventListener('mouseover', (event) => {
        const node = getModalTooltipNode(event);
        if (!node) return;

        const title = node.getAttribute('title');
        if (!title) return;

        const rect = node.getBoundingClientRect();
        const tooltip = getTooltipElement();
        tooltip.textContent = title;
        tooltip.style.left = `${window.scrollX + rect.left + rect.width / 2}px`;
        tooltip.style.top = `${window.scrollY + rect.bottom + 4}px`;
        tooltip.style.opacity = '0.9';
        node.classList.add('hover');
    }, true);

    document.addEventListener('mouseout', (event) => {
        const node = getModalTooltipNode(event);
        if (!node) return;

        const relatedTarget = event instanceof MouseEvent ? event.relatedTarget : null;
        if (relatedTarget instanceof Node && node.contains(relatedTarget)) return;

        getTooltipElement().style.opacity = '0';
        node.classList.remove('hover');
    }, true);

    modalTooltipFallbackInitialized = true;
}

async function enhanceDiagram() {
    const { init, enhance } = await import('mermaid-diagram-pan-zoom');
    if (!mermaidEnhancementsInitialized) {
        init({
            containerSelector: '.mermaid-pan-zoom-container',
            sourceAttribute: 'data-mermaid-source',
            enableCopy: true,
            enableExpand: true,
            enableInlineWheelZoom: true,
            enableWheelZoom: true,
            enableZoomControls: true,
            wheelZoomSensitivity: 0.3,
            panZoomOptions: {
                minZoom: 0.2,
                maxZoom: 8,
                zoomScaleSensitivity: 0.3,
            },
        });
        mermaidEnhancementsInitialized = true;
    }
    enhance();
}

async function renderDiagram() {
    if (!container.value) return;

    try {
        const mermaid = (await import('mermaid')).default;
        mermaid.initialize({
            startOnLoad: false,
            securityLevel: 'loose',
            theme: isDark.value ? 'dark' : 'default',
        });

        const id = `mermaid-${Math.random().toString(36).slice(2)}`;
        const { svg, bindFunctions } = await mermaid.render(id, source.value);
        container.value.innerHTML = svg;
        bindFunctions?.(container.value);
        await enhanceDiagram();
        error.value = '';
    } catch (err) {
        container.value.innerHTML = '';
        const fallback = lang.value === 'es' ? 'No se pudo mostrar el diagrama' : lang.value.startsWith('zh') ? '图示渲染失败' : 'Could not render the diagram';
        error.value = err instanceof Error ? err.message : fallback;
    }
}

onMounted(() => {
    initModalTooltipFallback();
    void nextTick(renderDiagram);
});

watch([source, isDark], () => {
    void nextTick(renderDiagram);
});
</script>
