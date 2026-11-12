<template>
    <ElSubMenu v-if="item.children" :index="item.id" :class="{ 'navigation-entry--icon': item.iconOnly, 'navigation-entry--primary': item.primary }" :data-navigation-id="item.id" :aria-label="item.label" :title="item.label">
        <template #title>
            <NavigationLabel :item="item" />
        </template>
        <NavigationEntry v-for="child in item.children" :key="child.id" :item="child" :active="active" @activate="emit('activate', $event)" @navigate="emit('navigate')" />
    </ElSubMenu>
    <ElMenuItem v-else :index="item.id" :class="{ 'navigation-entry--primary': item.primary }" :data-navigation-id="item.id" :aria-label="item.label" :title="item.label">
        <component :is="item.component" v-if="item.component" class="navigation-control" compact />
        <NavigationControl v-else :item="item" :active="active" @activate="emit('activate', $event)" @navigate="emit('navigate')" />
    </ElMenuItem>
</template>

<script setup lang="ts">
import { ElMenuItem, ElSubMenu } from 'element-plus';
import type { PropType } from 'vue';

import NavigationControl from './NavigationControl.vue';
import NavigationLabel from './NavigationLabel.vue';
import type { NavigationItem } from './types';

defineProps({
    item: { type: Object as PropType<NavigationItem>, required: true },
    active: { type: String, required: true },
});
const emit = defineEmits<{ activate: [id: string]; navigate: [] }>();
</script>
