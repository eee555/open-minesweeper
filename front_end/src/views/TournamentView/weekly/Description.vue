<template>
    <div>
        {{ t('local.line1', { format: formatName }) }}
    </div>
    <div>
        {{ t('local.line2') }}
    </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { Tournament } from '@/utils/tournaments';
import { weeklyFormatNames, WeeklyTournamentFormat } from '@/utils/weeklyFormat';

const props = defineProps({ tournamentFormat: { type: String as PropType<WeeklyTournamentFormat>, default: WeeklyTournamentFormat.Classic } });
const formatName = computed(() => Tournament.getLocalString(weeklyFormatNames[props.tournamentFormat], locale.value));

const i18nMessages = {
    'zh-cn': { local: {
        line1: '本场为{format}赛制。在比赛期间任选2小时参赛。参赛后2小时区间内上传（以服务器接收时间为准）的合格录像中，取成绩最好的5局中级、2局高级，计算总成绩。',
        line2: '局数不够的，中级按照60秒，高级按照240秒补全。',
    } },
    en: { local: {
        line1: 'Format: {format}. Choose any 2-hour interval during the tournament. Among eligible videos received by the server within 2 hours after registration, sum up the best 5 intermediate games and 2 expert games.',
        line2: 'The default scores are 60s for intermediate and 240s for expert, when there are not enough games uploaded.',
    } },
    es: { local: {
        line1: 'Formato: {format}. Elige cualquier intervalo de 2 horas durante el torneo. Entre los videos válidos recibidos por el servidor durante las 2 horas tras el registro, suma los 5 mejores juegos intermedios y 2 juegos expertos.',
        line2: 'Los puntajes por defecto son de 60 segundos para intermedios y 240 segundos para expertos, cuando no hay suficientes juegos subidos.',
    } },
};

const { t, locale } = useI18n({ messages: i18nMessages });
</script>
