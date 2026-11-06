import { AccountLinkPlatform } from '@/utils/accountlinks';
import { Classic95Icon } from '@/utils/assets';

export const platforms = [
    { id: AccountLinkPlatform.Saolei, src: 'https://saolei.wang/icon.svg', mask: false, private: false },
    { id: AccountLinkPlatform.MSGames, src: 'https://minesweepergame.com/favicon.ico', mask: false, private: false },
    { id: AccountLinkPlatform.WoM, src: 'https://minesweeper.online/img/minesweeper-online.svg', mask: false, private: false },
    { id: AccountLinkPlatform.Bilibili, src: 'https://www.bilibili.com/favicon.ico', mask: false, private: false },
    { id: AccountLinkPlatform.Mineracer, src: 'https://mineracer.com/favicon.svg', mask: false, private: false },
    { id: AccountLinkPlatform.Classic, src: Classic95Icon, mask: false, private: false },
    { id: AccountLinkPlatform.QQ, src: 'https://wiki.connect.qq.com/wp-content/uploads/2013/10/03_qq_symbol-1-250x300.png', mask: false, private: true },
    // Font Awesome Free Brands SVG via npmmirror; CSS mask follows the theme color.
    { id: AccountLinkPlatform.Discord, src: 'https://registry.npmmirror.com/@fortawesome/fontawesome-free/6.7.2/files/svgs/brands/discord.svg', mask: true, private: true },
] as const;
