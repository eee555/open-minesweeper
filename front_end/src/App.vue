<template>
    <ElConfigProvider :locale="locale === 'es' ? es : undefined">
        <Menu>
            <main class="common-layout">
                <VideoPlayer />
                <VideoInfoProgress />
                <router-view />
                <Footer />
            </main>
        </Menu>

        <ElDialog
            v-if="false" v-model="notice_visible" draggable :lock-scroll="false" title="站长通知"
            :before-close="handle_notice_close" style="white-space: pre-wrap;" width="min(max(50%, 400px), 90vw)"
        >
            <span>{{ notice }}</span>
            <template #footer>
                <span class="dialog-footer">
                    <label class="checkbox">
                        <input v-model="never_show_notice" class="checkbox-input" type="checkbox">
                        <span>不再显示此对话框&nbsp;&nbsp;&nbsp;</span>
                    </label>
                    <BaseButtonConfirm @click="handle_notice_close()" />
                </span>
            </template>
        </ElDialog>
    </ElConfigProvider>
</template>

<script setup lang="ts">
import { useDark, useToggle } from '@vueuse/core';
import { ElConfigProvider, ElDialog } from 'element-plus';
import es from 'element-plus/es/locale/lang/es';
import { onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButtonConfirm from './components/common/BaseButtonConfirm.vue';
import Footer from './components/Footer.vue';
import VideoInfoProgress from './components/VideoInfoProgress.vue';
import VideoPlayer from './components/VideoPlayer/App.vue';
import { local } from './store';
import Menu from './views/Menu.vue';

const { locale } = useI18n();
const isDark = useDark();
useToggle(isDark);
watch(isDark, (v) => {
    local.value.darkmode = v;
});

// const player_visible = ref(false)
const notice_visible = ref(false);
const never_show_notice = ref(false);

const notice = ref(`
0、即日起，网站正式上线！！！
1、开源扫雷网是社区共建的扫雷排名网站。在这里，你可以上传扫雷录像参与全球排名；也希望有开发能力的雷友可以发挥专业能力，为网站贡献代码、增加功能。
2、软件下载链接在页面最下方。
3、网站运营完全依赖赞助，希望有能力的雷友给与力所能及的帮助和支持，我们不胜感激。
4、相关意见、问题和建议请移步至此处https://gitee.com/ee55/saolei_website/issues发表。
`);

onMounted(() => {
    const notice_hash = localStorage.getItem('notice');
    if (hash_code(notice.value) + '' != notice_hash) {
        notice_visible.value = true;
    }

    console.log(`
  开源扫雷网(openms.top)开发团队，期待您的加入: 2234208506@qq.com
  `);
    local.value.darkmode = isDark.value;
});

// const goback_home = () => {
//     router.push("/")
// }

// 站长通知关闭的回调
const handle_notice_close = () => {
    if (never_show_notice.value) {
        localStorage.setItem('notice', hash_code(notice.value) + '');
    }
    notice_visible.value = false;
};

function hash_code(t: string) {
    let hash = 0;
    if (t.length === 0) return hash;
    for (let i = 0; i < t.length; i++) {
        const chr = t.charCodeAt(i);
        hash = (hash << 5) - hash + chr;
        hash |= 0; // 32bit integer
    }
    return hash;
}
</script>

<style lang="less">
body {
    margin: 0;
}
</style>

<style lang="less" scoped>
.common-layout {
    box-sizing: border-box;
    min-height: 0;
    min-width: 0;
    overflow: auto;
    padding: 1rem;
}
</style>

<style lang="less">
// 傻逼PrimeVue的bug，开发者还不当回事
// https://github.com/primefaces/primevue/issues/4093
// ElementPlus也不支持表格分页，只能先吃着PrimeVue这坨屎
.p-datatable-filter-overlay-popover {
    z-index: 3000 !important;
}

.p-select-overlay {
    z-index: 3000 !important;
}
</style>
