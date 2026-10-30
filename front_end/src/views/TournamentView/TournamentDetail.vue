<template>
    <!-- eslint-disable-next-line vue/no-v-html, vue/no-v-text-v-html-on-component -->
    <h1 v-if="tournament.name" class="text" v-html="tournament.name" />
    <!-- eslint-disable-next-line vue/no-v-html, vue/no-v-text-v-html-on-component -->
    <h1 v-if="tournament.description" class="text" v-html="tournament.getLocalDescription(local.language)" />
    <BaseTable :empty="data.length === 0" :empty-text="t('ranking.empty')" :column-count="Math.max(1, columns.length)">
        <template v-if="columns.length > 0" #head>
            <tr>
                <th v-for="column in columns" :key="column" scope="col">
                    {{ column }}
                </th>
            </tr>
        </template>
        <tr v-for="(row, index) in data" :key="index">
            <td v-for="column in columns" :key="column">
                {{ row[column]?.toString() }}
            </td>
        </tr>
    </BaseTable>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseTable from '@/components/common/BaseTable.vue';
import { local } from '@/store';
import { Tournament } from '@/utils/tournaments';

const props = defineProps({
    tournament: {
        type: Tournament,
        default: () => new Tournament({}),
    },
    data: {
        type: Array as () => Record<string, unknown>[],
        default: () => [],
    },
});

const columns = computed(() => Object.keys(props.data[0] ?? {}));
const { t } = useI18n();
</script>
