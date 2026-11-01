export interface AccountDiscordResponse {
    id: string;
    parent: number;
    username: string;
    global_name: string;
    avatar?: string | null;
    banner?: string | null;
    accent_color?: number | null;
    public_flags?: number | null;
    update_time: string;
}

// Public profile badges from Discord's User Flags table. Keep unknown bits in public_flags.
const badgeBits = [
    [0, 'staff'], [1, 'partner'], [2, 'hypesquad'], [3, 'bugHunter1'],
    [6, 'bravery'], [7, 'brilliance'], [8, 'balance'], [9, 'earlySupporter'],
    [14, 'bugHunter2'], [17, 'developer'], [18, 'moderator'],
] as const;

function imageUrl(kind: 'avatars' | 'banners', id: string, hash: string): string | undefined {
    if (!(/^[1-9]\d*$/).test(id) || !(/^(a_)?[0-9a-f]{32}$/).test(hash)) return undefined;
    const extension = hash.startsWith('a_') ? 'gif' : 'png';
    return `https://cdn.discordapp.com/${kind}/${id}/${hash}.${extension}?size=${kind === 'avatars' ? 128 : 512}`;
}

export class AccountDiscord {
    public id: string;
    public username: string;
    public global_name: string;
    public avatar: string;
    public banner: string;
    public accent_color: number | null;
    public public_flags: number | null;
    public update_time: Date;

    public constructor(data: AccountDiscordResponse) {
        this.id = data.id;
        this.username = data.username;
        this.global_name = data.global_name;
        this.avatar = data.avatar ?? '';
        this.banner = data.banner ?? '';
        this.accent_color = data.accent_color ?? null;
        this.public_flags = data.public_flags ?? null;
        this.update_time = new Date(data.update_time);
    }

    public get avatarUrl(): string | undefined {
        return imageUrl('avatars', this.id, this.avatar);
    }

    public get bannerUrl(): string | undefined {
        return imageUrl('banners', this.id, this.banner);
    }

    public get accentColor(): string | undefined {
        if (this.accent_color === null || this.accent_color < 0 || this.accent_color > 0xFFFFFF) return undefined;
        return '#' + this.accent_color.toString(16).padStart(6, '0');
    }

    public get badgeNames(): string[] {
        const flags = this.public_flags;
        if (flags === null) return [];
        return badgeBits.filter(([bit]) => Math.floor(flags / (2 ** bit)) % 2 === 1).map(([, name]) => name);
    }
}
