const saoleiProfile = (id: string | number): string => 'http://saolei.wang/Player/Index.asp?Id=' + id;
const msgamesProfile = (id: string | number): string => 'https://minesweepergame.com/profile.php?pid=' + id;
const womProfile = (id: string | number): string => 'https://minesweeper.online/player/' + id;
const qqProfile = (id: string | number): string => 'https://user.qzone.qq.com/' + id;
const bilibiliProfile = (id: string | number): string => 'https://space.bilibili.com/' + id;
const mineracerProfile = (): string => 'https://mineracer.com/';
const discordProfile = (id: string | number): string => 'https://discord.com/users/' + id;

export const AccountLinkPlatform = {
    Bilibili: 'B',
    Discord: 'd',
    Mineracer: 'm',
    MSGames: 'a',
    QQ: 'q',
    Saolei: 'c',
    WoM: 'w',
} as const;
export type AccountLinkPlatform = typeof AccountLinkPlatform[keyof typeof AccountLinkPlatform];

export const manualAccountLinkPlatforms = [
    AccountLinkPlatform.Bilibili,
    AccountLinkPlatform.MSGames,
    AccountLinkPlatform.QQ,
    AccountLinkPlatform.Saolei,
    AccountLinkPlatform.WoM,
] as const;

interface AccountLinkPlatformProfile {
    url: string;
    profile: (id: string | number) => string;
}

export const platformlist: Record<AccountLinkPlatform, AccountLinkPlatformProfile> = {
    [AccountLinkPlatform.Discord]: { url: 'https://discord.com/', profile: discordProfile },
    [AccountLinkPlatform.Bilibili]: { url: 'https://www.bilibili.com/', profile: bilibiliProfile },
    [AccountLinkPlatform.Mineracer]: { url: 'https://mineracer.com/', profile: mineracerProfile },
    [AccountLinkPlatform.MSGames]: { url: 'https://minesweepergame.com/', profile: msgamesProfile },
    [AccountLinkPlatform.Saolei]: { url: 'http://saolei.wang/', profile: saoleiProfile },
    [AccountLinkPlatform.QQ]: { url: 'https://im.qq.com/index/', profile: qqProfile },
    [AccountLinkPlatform.WoM]: { url: 'https://minesweeper.online/', profile: womProfile },
};
