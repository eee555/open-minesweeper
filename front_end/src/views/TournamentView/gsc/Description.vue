<template>
    <div>
        {{ t('local.line1') }}
    </div>
    <div>
        {{ t('local.line2') }}
    </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

const i18nMessages = {
    'zh-cn': { local: {
        line1: '比赛期间上传（以服务器接收时间为准）的所有录像中，取成绩最好的20局初级（bv>=10）、12局中级（bv>=30）、5局高级（bv>=100），计算总成绩。',
        line2: '局数不够的，初级按照10秒，中级按照60秒，高级按照240秒补全。',
    } },
    en: { local: {
        line1: 'Among all videos uploaded during (depending on when the server receives the file) the tournament, sum up the best 20 beginner (bv >= 10) games, 12 intermediate (bv >= 30) games and 5 expert (bv >= 100) games.',
        line2: 'The default scores are 10s for beginner, 60s for intermediate and 240s for expert, when there are not enough games uploaded.',
    } },
    es: { local: {
        line1: 'Entre todos los videos subidos durante el torneo (dependiendo del momento en que el servidor reciba el archivo), suma los 20 mejores juegos para principiantes (bv >= 10), 12 intermedios (bv >= 30) y 5 expertos (bv >= 100).',
        line2: 'Los puntajes por defecto son de 10 segundos para principiantes, 60 segundos para intermedios y 240 segundos para expertos, cuando no hay suficientes juegos subidos.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
