import { AccountBilibili } from './bilibili';
import type { AccountBilibiliResponse } from './bilibili';
import type { AccountLinkQueueResponse } from './common';
import { AccountDiscord } from './discord';
import type { AccountDiscordResponse } from './discord';
import { AccountMineracer } from './mineracer';
import type { AccountMineracerResponse } from './mineracer';
import { AccountMSGames } from './msgames';
import type { AccountMSGamesResponse } from './msgames';
import type { AccountLinkPlatform } from './platforms';
import { AccountQQ } from './qq';
import type { AccountQQResponse } from './qq';
import { AccountSaolei } from './saolei';
import type { AccountSaoleiResponse } from './saolei';
import { AccountWoM } from './wom';
import type { AccountWoMResponse } from './wom';

export interface AccountLinksResponse {
    d?: AccountDiscordResponse | null;
    summary: AccountLinkQueueResponse[];
    B: AccountBilibiliResponse | null;
    m: AccountMineracerResponse | null;
    c: AccountSaoleiResponse | null;
    a: AccountMSGamesResponse | null;
    w: AccountWoMResponse | null;
    q: AccountQQResponse | null;
}

export class AccountLinks {
    public d?: AccountDiscord;
    public summary: AccountLinkQueueResponse[] = [];
    public B?: AccountBilibili;
    public m?: AccountMineracer;
    public c?: AccountSaolei;
    public a?: AccountMSGames;
    public w?: AccountWoM;
    public q?: AccountQQ;

    public constructor(data?: AccountLinksResponse) {
        if (data === undefined) return;

        this.summary = data.summary;
        this.d = data.d == null ? undefined : new AccountDiscord(data.d);
        this.B = data.B === null ? undefined : new AccountBilibili(data.B);
        this.m = data.m === null ? undefined : new AccountMineracer(data.m);
        this.c = data.c === null ? undefined : new AccountSaolei(data.c);
        this.a = data.a === null ? undefined : new AccountMSGames(data.a);
        this.w = data.w === null ? undefined : new AccountWoM(data.w);
        this.q = data.q === null ? undefined : new AccountQQ(data.q);
    }

    public get count(): number {
        return this.summary.length;
    }

    public get verifiedSummary(): AccountLinkQueueResponse[] {
        return this.summary.filter((accountlink) => accountlink.verified);
    }

    public getSummary(platform: AccountLinkPlatform): AccountLinkQueueResponse | undefined {
        return this.summary.find((accountlink) => accountlink.platform === platform);
    }

    public has(platform: AccountLinkPlatform): boolean {
        return this.getSummary(platform) !== undefined;
    }

    public addSummary(accountlink: AccountLinkQueueResponse): void {
        const index = this.summary.findIndex((current) => current.platform === accountlink.platform);
        if (index === -1) {
            this.summary.push(accountlink);
        } else {
            this.summary[index] = accountlink;
        }
    }
}
