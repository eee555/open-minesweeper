import { createI18n } from 'vue-i18n';
import type { DefineLocaleMessage } from 'vue-i18n';

import de from './locales/de';
import dev from './locales/dev';
import en from './locales/en';
import es from './locales/es';
import pl from './locales/pl';
import zhCn from './locales/zh-cn';

/**
 * 获取所有语言
 */
function getMessages(): Record<string, DefineLocaleMessage> {
    const messages: Record<string, DefineLocaleMessage> = {};
    messages[dev.local] = dev;
    messages[zhCn.local] = zhCn;
    messages[de.local] = de;
    messages[en.local] = en;
    messages[es.local] = es;
    messages[pl.local] = pl;
    return messages;
}

/**
 * 获取默认语言
 */
function getDefaultLocale() {
    return 'en';
}

/**
 * 配置 Vue I18n，开发工具参见：https://vue-i18n.intlify.dev/ecosystem/tools.html
 */
export default createI18n({
    legacy: false,
    fallbackLocale: {
        'zh-cn': ['dev'],
        en: ['dev'],
        es: ['en'],
        de: ['en'],
        pl: ['en'],
        'zh-tw': ['zh-cn'],
    },
    fallbackWarn: false,
    missingWarn: false,
    warnHtmlMessage: false,
    locale: getDefaultLocale(),
    messages: getMessages(),
});
