<template>
    {{ t('prop.tournamentId') }}
    &nbsp;
    <ElInputNumber v-model="tournamentId" :min="0" :controls="false" />
    &nbsp;
    <BaseButton @click="refreshTournamentInfo">
        {{ t('button.query') }}
    </BaseButton>
    <br>
    <template v-if="tournament">
        {{ t('prop.status') }}
        &nbsp;
        <TournamentStateIcon :state="tournament.getDisplayState(globalNow)" />
        <br>
        {{ t('prop.start_time') }}
        &nbsp;
        {{ tournament.startDate }}
        <br>
        {{ t('prop.end_time') }}
        &nbsp;
        {{ tournament.endDate }}
        <br>
        {{ t('local.review') }}
        <BaseButton class="square-button" type="success" size="small" :aria-label="t('button.approve')" :disabled="!tournament.canValidate" @click="validateTournament(true)">
            <BaseIconTick />
        </BaseButton>
        <BaseButton class="square-button" type="danger" size="small" :aria-label="t('button.revokeApproval')" :disabled="!tournament.canInvalidate" @click="validateTournament(false)">
            <BaseIconClose />
        </BaseButton>
        <br>
        {{ t('prop.name') }}
        <VCodeBlock v-if="tournament" :code="JSON.stringify(tournament.name)" lang="json" />
        {{ t('prop.description') }}
        <VCodeBlock v-if="tournament.description" :code="JSON.stringify(tournament.description)" lang="json" />
    </template>
</template>

<script setup lang="ts">
import { ElInputNumber } from 'element-plus';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import VCodeBlock from '@/components/common/BaseCodeBlock.vue';
import { BaseIconClose, BaseIconTick } from '@/components/common/icon';
import { httpErrorNotification, successNotification } from '@/components/Notifications';
import TournamentStateIcon from '@/components/widgets/TournamentStateIcon.vue';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { globalNow } from '@/utils/datetime';
import { Tournament } from '@/utils/tournaments';

const { proxy } = useCurrentInstance();

const tournamentId = ref<number>(0);
const tournament = ref<Tournament | null>(null);

type LocalizedString = string | Partial<Record<string, string>>;

interface TournamentResponseData {
    [key: string]: unknown;
    id?: number;
    name?: LocalizedString;
    description?: LocalizedString;
    start_time?: string | Date | null;
    end_time?: string | Date | null;
    subclass?: ConstructorParameters<typeof Tournament>[0]['subclass'];
    data?: ConstructorParameters<typeof Tournament>[0]['data'];
    host_id?: number;
    state?: ConstructorParameters<typeof Tournament>[0]['state'];
}

function refreshTournamentInfo() {
    if (!tournamentId.value) {
        tournament.value = null;
        return;
    }
    proxy.$axios.get<TournamentResponseData>('/api/tournament/get', { params: { tournament_id: tournamentId.value } }).then(({ data }) => {
        tournament.value = new Tournament(data);
    }).catch((e: unknown) => {
        tournament.value = null;
        httpErrorNotification(e);
    });
}

function validateTournament(valid: boolean) {
    if (!tournamentId.value) return;
    proxy.$axios.post('/api/tournament/validate', {
        id: tournamentId.value,
        valid: valid,
    }).then((response) => {
        refreshTournamentInfo();
        successNotification(response);
    }).catch(httpErrorNotification);
}

const i18nMessages = {
    'zh-cn': { local: {
        review: '审核',
    } },
    en: { local: {
        review: 'Review',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
