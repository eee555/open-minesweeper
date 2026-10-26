<template>
    <h1>
        {{ tournament.getLocalName(local.language) }}
        <TournamentStateIcon :state="tournament.getDisplayState(globalNow)" />
    </h1>
    {{ t('local.schedule') }}{{ t('punct.colon') }}
    <span>
        {{ tournament.displayStartTime() }}
        &nbsp;~&nbsp;
        {{ tournament.displayEndTime() }}
    </span>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

import TournamentStateIcon from '@/components/widgets/TournamentStateIcon.vue';
import { local } from '@/store';
import { globalNow } from '@/utils/datetime';
import { Tournament } from '@/utils/tournaments';

defineProps({
    tournament: { type: Tournament, required: true },
});

const i18nMessages = {
    'zh-cn': { local: {
        schedule: '赛程',
    } },
    en: { local: {
        schedule: 'Schedule',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
