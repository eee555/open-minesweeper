import { useLocalStorage } from '@vueuse/core';

const localDefaultSettings = {
    darkmode: matchMedia('(prefers-color-scheme: dark)').matches,
    experimental: false,
    colored: false,
    language: navigator.language.toLocaleLowerCase(),
    navigation_layout: 'top' as 'top' | 'sidebar',
    notification_duration: 4500,
    vienna_logo_legacy: false,
    autoUploadAfterParse: false,
    autoRemoveAfterUpload: false,
    nameFormat: 'first-last' as 'first-last' | 'last-first',
    playerNameShowAvatar: false,
    playerNameFormat: 'name1' as 'name1' | 'name1 (name2)',
    playerName1: 'username' as 'realname' | 'international' | 'username',
    playerName2: 'realname' as 'realname' | 'international' | 'username',
};

export type LocalSettings = typeof localDefaultSettings;
export const local = useLocalStorage('local', localDefaultSettings, { mergeDefaults: true });

// Remove the retired help toggle from existing browser settings.
Reflect.deleteProperty(local.value, 'tooltip_show');
