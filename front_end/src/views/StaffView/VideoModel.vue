<template>
    <div>
        {{ t('prop.videoId') }}
        <ElInputNumber v-model="videoid" :controls="false" :min="0" />
        <BaseButton @click="getVideo">
            {{ t('button.query') }}
        </BaseButton>
        <BaseButton @click="previewVideo">
            {{ t('button.play') }}
        </BaseButton>
        <BaseButton @click="updateVideo(videoid)">
            {{ t('button.update') }}
        </BaseButton>
        <BaseButton @click="removeNewest(videoid)">
            {{ t('local.removeNewest') }}
        </BaseButton>
    </div>
    <div>
        {{ t('local.field') }}<ElSelect v-model="videofield">
            <ElOption v-for="field in videofieldlist" :key="field" :label="t(`prop.${field}`)" :value="field" />
        </ElSelect>
    </div>
    <div>
        {{ t('prop.value') }}<ElInput v-model="videovalue" />
    </div>
    <div>
        <BaseButton @click="setVideo(videoid, videofield, videovalue)">
            {{ t('button.save') }}
        </BaseButton>
    </div>
    <ElDescriptions :title="t('local.videoModel')">
        <ElDescriptionsItem v-for="(value, field) in videomodel" :key="field" :label="videoFieldLabel(field)">
            {{ value }}
        </ElDescriptionsItem>
    </ElDescriptions>
</template>

<script lang="ts" setup>
import type { AxiosResponse } from 'axios';
import { ElDescriptions, ElDescriptionsItem, ElInput, ElInputNumber, ElOption, ElSelect } from 'element-plus';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { httpErrorNotification, successNotification } from '@/components/Notifications';
import { preview } from '@/utils/common/PlayerDialog';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import type { MS_Software } from '@/utils/ms_const';
import { MS_Softwares } from '@/utils/ms_const';

const { proxy } = useCurrentInstance();
const globalI18n = useI18n({ useScope: 'global' });

const videoid = ref(0);
const videofield = ref('');
const videovalue = ref('');
const videofieldlist = ['player', 'upload_time', 'state']; // 可以修改的域列表
const videomodel = ref<Record<string, unknown>>({});
const softwareSet = new Set<unknown>(MS_Softwares);

const getVideo = () => {
    proxy.$axios.get<Record<string, unknown>>(`/api/video/admin/detail/${videoid.value}`).then(
        function (response) {
            videomodel.value = response.data;
        },
    ).catch(httpErrorNotification);
};

function setVideoResponse(response: AxiosResponse<unknown>) {
    successNotification(response);
    getVideo();
}

const setVideo = (id: number, field: string, value: string) => {
    proxy.$axios.post<unknown>('video/set/', { id: id, field: field, value: value }).then(setVideoResponse).catch(httpErrorNotification);
};

const updateVideo = (id: number) => {
    proxy.$axios.post<unknown>('video/update/', { id: id }).then(setVideoResponse).catch(httpErrorNotification);
};

const removeNewest = (id: number) => {
    proxy.$axios.post<unknown>('/api/video/newest_queue/remove', { id: id }).then(setVideoResponse).catch(httpErrorNotification);
};

function previewVideo() {
    const { software } = videomodel.value;
    void preview(videoid.value, softwareSet.has(software) ? software as MS_Software : undefined);
}

function videoFieldLabel(field: string) {
    const key = `prop.${field}`;
    return globalI18n.te(key, locale.value) || globalI18n.te(key, 'en') || globalI18n.te(key, 'dev') ? t(key) : field;
}

const i18nMessages = {
    'zh-cn': { local: {
        removeNewest: '从最新录像中移除',
        field: '字段',
        videoModel: '录像信息（VideoModel）',
    } },
    en: { local: {
        removeNewest: 'Remove from latest videos',
        field: 'Field',
        videoModel: 'Video information (VideoModel)',
    } },
};

const { t, locale } = useI18n({ messages: i18nMessages });
</script>
