export interface AccountDiscordResponse {
    id: string;
    parent: number;
}

export function isDiscordUserId(value: string): boolean {
    return (/^[1-9][0-9]{0,19}$/).test(value);
}

export class AccountDiscord {
    public id = '';
    public parent = 0;

    public constructor(data?: AccountDiscordResponse) {
        if (data === undefined) return;
        this.id = data.id;
        this.parent = data.parent;
    }
}
