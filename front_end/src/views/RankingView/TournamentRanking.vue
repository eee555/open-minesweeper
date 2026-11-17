<template>
    <section>
        <select v-model="selectedRankingName" :aria-label="t('local.ranking')" class="base-select tournament-ranking-selector">
            <option v-for="name in rankingNames" :key="name" :value="name">
                {{ t(`local.${name}`) }}
            </option>
        </select>
        <RouterView v-slot="{ Component }">
            <component :is="Component" :key="route.name" />
        </RouterView>
    </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterView, useRoute, useRouter } from 'vue-router';

const rankingNames = ['overall', 'gsc', 'weekly', 'weekly_eff'] as const;
const route = useRoute();
const router = useRouter();
const selectedRankingName = computed<typeof rankingNames[number]>({
    get: () => rankingNames.find((name) => route.name === `ranking_tournament_${name}`) ?? 'overall',
    set: (name) => {
        void router.push({ name: `ranking_tournament_${name}` });
    },
});
const i18nMessages = {
    'zh-cn': { local: {
        ranking: '比赛排行榜', overall: '总榜', gsc: 'GSC', weekly: '竞速打卡赛', weekly_eff: '效率打卡赛',
    } },
    en: { local: {
        ranking: 'Tournament ranking', overall: 'Overall', gsc: 'GSC', weekly: 'Speed Weekly', weekly_eff: 'Efficiency Weekly',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.tournament-ranking-selector {
    width: 14rem;
    max-width: 100%;
    margin-bottom: 1rem;
}
</style>
