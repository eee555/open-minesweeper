import $axios from '@/http';
import type { AccountLinkPlatform } from '@/utils/accountlinks/platforms';

export type UserDirectoryPlatform = typeof AccountLinkPlatform.Saolei | typeof AccountLinkPlatform.MSGames | typeof AccountLinkPlatform.WoM | typeof AccountLinkPlatform.Mineracer;

export interface UserVideoStatistics {
    video_num_total: number;
    video_num_tournament: number;
    video_num_all: number;
    video_size_total: number;
    video_size_tournament: number;
    video_size_all: number;
}

export type UserDirectorySort = 'id' | keyof UserVideoStatistics;

export interface DirectoryUser {
    id: number;
    is_memorial?: boolean;
    date_joined: string;
    accounts: Partial<Record<UserDirectoryPlatform, string>>;
    statistics: UserVideoStatistics;
}

export interface UserDirectoryFilters {
    platform: UserDirectoryPlatform | '';
    id: string;
}

export interface UserDirectoryQuery extends UserDirectoryFilters {
    page: number;
    page_size: number;
    sort: UserDirectorySort;
    reverse: boolean;
}

export interface UserDirectoryPage {
    count: number;
    users: DirectoryUser[];
}

export async function fetchUserDirectory(params: UserDirectoryQuery, signal: AbortSignal): Promise<UserDirectoryPage> {
    const { data } = await $axios.get<UserDirectoryPage>('/api/userprofile/query', { params, signal });
    return data;
}
