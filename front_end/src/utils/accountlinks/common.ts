import type { AccountLinkPlatform } from './platforms';

export interface AccountLinkQueueResponse {
    id: number;
    platform: AccountLinkPlatform;
    identifier: string;
    userprofile: number;
    verified: boolean;
}

export interface AccountLinkQueuePageResponse {
    count: number;
    page: number;
    page_size: number;
    items: AccountLinkQueueResponse[];
}
