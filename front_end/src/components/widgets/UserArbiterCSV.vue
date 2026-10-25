<template>
    <BaseButton :disabled="id == 0" @click="clickExportJSON">
        {{ t('profile.exportJSON') }}&nbsp;
        <ElTooltip :content="t('profile.exportJSONTooltip')" raw-content>
            <ElIcon>
                <QuestionFilled />
            </ElIcon>
        </ElTooltip>
    </BaseButton>
    <BaseButton :disabled="id == 0" @click="clickExportCSV">
        {{ t('profile.exportArbiterCSV') }}&nbsp;
        <ElTooltip :content="t('profile.exportArbiterCSVTooltip')" raw-content>
            <ElIcon>
                <QuestionFilled />
            </ElIcon>
        </ElTooltip>
    </BaseButton>
</template>

<script setup lang="ts">
import { ElIcon, ElTooltip } from 'element-plus';
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { httpErrorNotification } from '../Notifications';

import BaseButton from '@/components/common/BaseButton.vue';
import { ArrayUtils } from '@/utils/arrays';
import useCurrentInstance from '@/utils/common/useCurrentInstance';

const props = defineProps({
    id: {
        type: Number,
        default: 0,
    },
});

const { t } = useI18n();

const { proxy } = useCurrentInstance();

interface DataEntry {
    mode: string;
    level: string;
    timems: number;
    bv: number;
    bvs: number;
    upload_time: string;
    right_ce: number | null;
    video__cell0: number;
    video__cell1: number;
    video__cell2: number;
    video__cell3: number;
    video__cell4: number;
    video__cell5: number;
    video__cell6: number;
    video__cell7: number;
    video__cell8: number;
    video__left: number;
    video__right: number;
    video__double: number;
    video__op: number;
    video__isl: number;
    video__path: number;
}

const data = ref([] as DataEntry[]);

watch(props, () => {
    data.value = [];
});

async function fetchData(id: number) {
    await proxy.$axios.get<DataEntry[]>('/api/video/query_by_id', {
        params: {
            id: id,
        },
    }).then(function (response) {
        data.value = response.data;
    }).catch(httpErrorNotification);
}

function generateArbiterCSV(raw: DataEntry[]) {
    if (ArrayUtils.isEmpty(raw)) return '';
    const csvdata = ['Day,Month,Year,Hour,Min,Sec,mode,Time,BBBV,BBBVs,style,cell0,cell1,cell2,cell3,cell4,cell5,cell6,cell7,cell8,Lcl,Rcl,Dcl,Leff,Reff,Deff,Openings,Islands,Path,GZiNi,HZiNi'];
    for (const v of raw) {
        if (v.mode != '00') continue;
        const date = new Date(v.upload_time);
        const row: (string | number)[] = [date.getUTCDate(), date.getUTCMonth() + 1, date.getUTCFullYear(), date.getUTCHours(), date.getUTCMinutes(), date.getUTCSeconds()];
        switch (v.level) {
            case 'e': row.push(3); break;
            case 'i': row.push(2); break;
            case 'b': row.push(1); break;
            default: console.error('未知级别');
        }
        row.push((v.timems / 1000).toFixed(2));
        row.push(v.bv);
        row.push(v.bvs.toFixed(2));

        if (v.right_ce === 0) row.push('NF');
        else row.push('Flag');

        row.push(v.video__cell0, v.video__cell1, v.video__cell2, v.video__cell3, v.video__cell4, v.video__cell5, v.video__cell6, v.video__cell7, v.video__cell8);
        row.push(v.video__left, v.video__right, v.video__double, 0, 0, 0);
        row.push(v.video__op, v.video__isl);
        row.push(Math.round(v.video__path));
        row.push(0, 0);
        csvdata.push(row.join());
    }
    return csvdata.join('\n');
}

// Credit: ChatGPT
function downloadCSV(csv: string) {
    if (csv === '') return;
    // Create a Blob from the CSV data
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);

    // Create a temporary anchor element
    const a = document.createElement('a');
    a.href = url;
    a.download = 'stats_csv.csv'; // Set the file name

    // Append the anchor to the body
    document.body.appendChild(a);
    a.click(); // Trigger the download
    document.body.removeChild(a); // Remove the anchor after download

    // Release the object URL
    URL.revokeObjectURL(url);
}

function downloadJSON(json: string) {
    if (json === '') return;
    // Create a Blob from the CSV data
    const blob = new Blob([json], { type: 'text/json' });
    const url = URL.createObjectURL(blob);

    // Create a temporary anchor element
    const a = document.createElement('a');
    a.href = url;
    a.download = 'stats_json.json'; // Set the file name

    // Append the anchor to the body
    document.body.appendChild(a);
    a.click(); // Trigger the download
    document.body.removeChild(a); // Remove the anchor after download

    // Release the object URL
    URL.revokeObjectURL(url);
}

async function clickExportCSV() {
    if (data.value.length === 0) await fetchData(props.id);
    if (data.value.length === 0) return;
    downloadCSV(generateArbiterCSV(data.value));
}

async function clickExportJSON() {
    if (data.value.length === 0) await fetchData(props.id);
    if (data.value.length === 0) return;
    downloadJSON(JSON.stringify(data.value));
}
</script>
