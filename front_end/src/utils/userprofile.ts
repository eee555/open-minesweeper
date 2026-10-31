import { VideoAbstract } from './videoabstract';
import type { VideoAbstractData } from './videoabstract';

export const HIDDEN_NAME = 'hidden';

export function hasRealname(value: string): boolean {
    return value.trim() !== '' && value.trim() !== '匿名';
}

export function hasHiddenName(user: Pick<UserProfileData, 'realname' | 'firstname' | 'lastname'>): boolean {
    return [user.realname, user.firstname, user.lastname].includes(HIDDEN_NAME);
}

export interface UserProfileData {
    id?: number;
    username?: string;
    realname?: string;
    firstname?: string;
    lastname?: string;
    can_hide_realname?: boolean;
    hide_realname?: boolean;
    is_banned?: boolean;
    is_staff?: boolean;
    is_superuser?: boolean;
    is_memorial?: boolean;
    country?: string;
    signature?: string;
    last_change_avatar?: string | Date | null;
    last_change_signature?: string | Date | null;
    left_avatar_n?: number;
    left_signature_n?: number;
    identifiers?: string[];
    videos?: VideoAbstractData[];
}

export class UserProfile {
    public id = 0;
    public username = '';
    public realname = '';
    public firstname = '';
    public lastname = '';
    public can_hide_realname = false;
    public hide_realname = false;
    public is_banned = false;
    public is_staff = false;
    public is_superuser = false;
    public is_memorial = false;
    public country = '';
    public signature = '';
    public last_change_avatar: Date = new Date();
    public last_change_signature: Date = new Date();
    public left_avatar_n = 0;
    public left_signature_n = 0;
    public accountlink: unknown[] = [];
    public identifiers?: string[];
    public videos?: VideoAbstract[];
    public videosViewerKey?: string;
    public videosRevision?: number;

    public constructor(data?: UserProfileData) {
        if (data === undefined) return;
        this.id = data.id ?? 0;
        this.username = data.username ?? '';

        if (data.realname === '匿名') this.realname = '';
        else this.realname = data.realname ?? '';

        this.firstname = data.firstname ?? '';
        this.lastname = data.lastname ?? '';
        this.can_hide_realname = data.can_hide_realname ?? false;
        this.hide_realname = data.hide_realname ?? false;
        this.is_banned = data.is_banned ?? false;
        this.is_staff = data.is_staff ?? false;
        this.is_superuser = data.is_superuser ?? false;
        this.is_memorial = data.is_memorial ?? false;
        this.country = data.country ?? '';
        this.signature = data.signature ?? '';

        this.last_change_avatar = new Date(data.last_change_avatar ?? Date.now());
        this.last_change_signature = new Date(data.last_change_signature ?? Date.now());

        this.left_avatar_n = data.left_avatar_n ?? 0;
        this.left_signature_n = data.left_signature_n ?? 0;

        this.identifiers = data.identifiers;
        this.videos = data.videos?.map((video) => new VideoAbstract(video));
    }

    public get isAnonymous(): boolean {
        return !hasHiddenName(this) && !hasRealname(this.realname);
    }

    public get isNameHidden(): boolean {
        return hasHiddenName(this) || (!this.isAnonymous && this.can_hide_realname && this.hide_realname);
    }

    public get hasInternationalName(): boolean {
        return !hasHiddenName(this) && this.firstname !== '' && this.lastname !== '';
    }

    public get canSetName(): boolean {
        return !hasHiddenName(this) && (this.isAnonymous || this.firstname === '' || this.lastname === '');
    }

    public get nextAvatarAvailable(): Date {
        if (this.left_avatar_n > 0) return this.last_change_avatar;
        const year = this.last_change_avatar.getUTCFullYear();
        const targetTimestamp = Date.UTC(year + 1, 0, 1, 0, 0, 0);
        return new Date(targetTimestamp);
    }

    public get nextSignatureAvailable(): Date {
        if (this.left_signature_n > 0) return this.last_change_signature;
        const year = this.last_change_signature.getUTCFullYear();
        const month = this.last_change_signature.getUTCMonth();
        const targetTimestamp = Date.UTC(year, month + 1, 1, 0, 0, 0, 0);
        return new Date(targetTimestamp);
    }

    public newAvatarBudget(newDate: Date): number {
        return this.left_avatar_n + newDate.getUTCFullYear() - this.last_change_avatar.getUTCFullYear();
    }

    public newSignatureBudget(newDate: Date): number {
        return this.left_signature_n + 12 * (newDate.getUTCFullYear() - this.last_change_signature.getUTCFullYear()) + (newDate.getUTCMonth() - this.last_change_signature.getUTCMonth());
    }
}
