<template>
    <div class="canvas-box" :style="{ height: '32px' }" @click="refreshPic()">
        <span v-if="loading">
            {{ t('form.captchaLoading') }}
        </span>
        <img v-else-if="captchaUrl" :src="captchaUrl" alt="">
        <span v-else>
            {{ t('form.captchaLoadingFail') }}
        </span>
    </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { httpErrorNotification, unknownErrorNotification } from './Notifications';

import useCurrentInstance from '@/utils/common/useCurrentInstance';

const { proxy } = useCurrentInstance();

const { t } = useI18n();

const captchaUrl = ref('');
const hashkey = ref('');
const loading = ref(true);

const refreshPic = () => {
    loading.value = true;
    proxy.$axios.get('/userprofile/refresh_captcha/').then(function (response) {
        if (response.data.status == 100) {
            hashkey.value = response.data.hashkey;
            captchaUrl.value = import.meta.env.VITE_BASE_API + '/userprofile/captcha/image/' + hashkey.value + '/';
        } else {
            unknownErrorNotification(response.data);
            captchaUrl.value = '';
        }
        loading.value = false;
    }).catch((error: unknown) => {
        httpErrorNotification(error);
        captchaUrl.value = '';
        loading.value = false;
    });
};

onMounted(() => {
    refreshPic();
});

defineExpose({
    hashkey,
    refreshPic,
});
</script>

<style scoped>
.canvas-box {
	cursor: pointer;

	.id-canvas2 {
		height: 100%;
	}
}
</style>
