<template>
    <div>
        {{ t('prop.videoId') }}
        <ElInputNumber v-model="videoid" :controls="false" :min="0" :disabled="freezing" data-cy="video-id" />
        <BaseButton :disabled="freezing" data-cy="video-query" @click="getVideo">
            {{ t('button.query') }}
        </BaseButton>
        <BaseButton @click="previewVideo">
            {{ t('button.play') }}
        </BaseButton>
        <BaseButton :disabled="freezing" @click="updateVideo(videoid)">
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
        <BaseButton :disabled="freezing" @click="setVideo(videoid, videofield, videovalue)">
            {{ t('button.save') }}
        </BaseButton>
    </div>
    <form class="video-freeze" @submit.prevent="freezeVideo">
        <label for="video-freeze-reason">{{ t('local.freezeReason') }}</label>
        <ElInput id="video-freeze-reason" v-model="freezeReason" type="textarea" :rows="3" :disabled="freezing" data-cy="freeze-reason" />
        <BaseButton native-type="submit" type="danger" :loading="freezing" :disabled="videomodel.id !== videoid || !freezeReason.trim()" data-cy="freeze-video">
            {{ t('local.freezeVideo') }}
        </BaseButton>
    </form>
    <ElDescriptions :title="t('local.videoModel')" data-cy="video-detail">
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

const { proxy } = useCurrentInstance();
const globalI18n = useI18n({ useScope: 'global' });

const videoid = ref(0);
const videofield = ref('');
const videovalue = ref('');
const videofieldlist = ['player', 'upload_time', 'state']; // 可以修改的域列表
const videomodel = ref<Record<string, unknown>>({});
const freezeReason = ref('');
const freezing = ref(false);

const getVideo = () => {
    const id = videoid.value;
    proxy.$axios.get<Record<string, unknown>>(`/api/video/admin/detail/${id}`).then(
        function (response) {
            if (videoid.value !== id || freezing.value) return;
            videomodel.value = response.data;
            freezeReason.value = typeof response.data.video__freeze_reason === 'string' ? response.data.video__freeze_reason : '';
        },
    ).catch(httpErrorNotification);
};

async function freezeVideo() {
    if (freezing.value || videomodel.value.id !== videoid.value || !freezeReason.value.trim()) return;
    const id = videoid.value;
    const freeze_reason = freezeReason.value.trim();
    freezing.value = true;
    try {
        const access = await proxy.$axios.get<{ csrf_token: string }>('/api/video/admin/freeze');
        const response = await proxy.$axios.post<{ id: number; state: string; freeze_reason: string }>('/api/video/admin/freeze', { id, freeze_reason }, {
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': access.data.csrf_token },
        });
        videomodel.value = { ...videomodel.value, state: response.data.state, video__freeze_reason: response.data.freeze_reason };
        freezeReason.value = response.data.freeze_reason;
        successNotification(response);
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        freezing.value = false;
    }
}

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
    preview(videoid.value);
}

function videoFieldLabel(field: string) {
    if (field === 'video__freeze_reason') return t('local.freezeReason');
    const key = `prop.${field}`;
    return globalI18n.te(key, locale.value) || globalI18n.te(key, 'en') || globalI18n.te(key, 'dev') ? t(key) : field;
}

const i18nMessages = {
    'zh-cn': { local: {
        removeNewest: '从最新录像中移除',
        field: '字段',
        videoModel: '录像信息（VideoModel）',
        freezeReason: '冻结原因',
        freezeVideo: '冻结录像 / 更新冻结原因',
    } },
    en: { local: {
        removeNewest: 'Remove from latest videos',
        field: 'Field',
        videoModel: 'Video information (VideoModel)',
        freezeReason: 'Freeze reason',
        freezeVideo: 'Freeze video / update reason',
    } },
};

const { t, locale } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-freeze {
    display: grid;
    gap: 6px;
    margin-block: 8px;
}

.video-freeze button {
    justify-self: start;
}
</style>
