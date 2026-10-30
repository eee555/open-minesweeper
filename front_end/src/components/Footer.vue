<template>
    <footer class="site-footer">
        <div style="margin-bottom: 15px">
            <div>
                <div style="padding-bottom: 5px">
                    <strong>{{ t('local.links') }}</strong>
                </div>
                <div>
                    <a class="link text" href="https://mineracer.com/" target="_blank" rel="noopener noreferrer">
                        Mineracer
                    </a>
                </div>
                <div>
                    <a class="link text" href="http://saolei.wang" target="_blank" rel="noopener noreferrer">
                        扫雷网 saolei.wang
                    </a>
                </div>
                <div>
                    <a class="link text" href="https://minesweepergame.com" target="_blank" rel="noopener noreferrer">
                        Authoritative Minesweeper
                    </a>
                </div>
                <div>
                    <a class="link text" href="https://minesweeper.online" target="_blank" rel="noopener noreferrer">
                        Minesweeper.Online
                    </a>
                </div>
                <div>
                    <a class="link text" href="http://tapsss.com" target="_blank" rel="noopener noreferrer">
                        扫雷联萌 League of Minesweeper
                    </a>
                </div>
                <div>
                    <a class="link text" href="https://scoreganizer.net" target="_blank" rel="noopener noreferrer">
                        Scoreganizer
                    </a>
                </div>
            </div>
        </div>
        <div style="text-align: center">
            <span>Copyright @ 2023</span>
            <a class="link text" href="http://openms.top">
                开源扫雷网 openms.top
            </a>
            <span>　版权所有</span>
            <a class="link text" href="https://beian.miit.gov.cn/">
                苏ICP备2023056839号-1
            </a>
            <span style="width: 12px; display: inline-block" />
            <a
                class="link text"
                href="https://beian.mps.gov.cn/#/query/webSearch?code=32020602001691" rel="noopener noreferrer"
                target="_blank"
            >
                苏公网安备32020602001691
            </a>
        </div>
    </footer>
</template>

<script setup lang="ts">
import '@/styles/link.css';

import { useI18n } from 'vue-i18n';

/* 本地化 Localization */
const i18nMessage = {
    'zh-cn': { local: {
        links: '友链',
    } },
    en: { local: {
        links: 'Links',
    } },
};

const { t } = useI18n({ messages: i18nMessage });
</script>

<style scoped>
.site-footer {
    box-sizing: border-box;
    border-top: 1px solid var(--ui-border-color);
    margin-top: 24px;
    padding: 24px 1rem 0;
}
</style>
