export type ClassicAccountLinkStatus = 'none' | 'pending' | 'allow' | 'deny' | 'revoke' | 'expired' | 'conflict';

export interface AccountClassicResponse {
    id: number;
    parent: number;
    update_time: string;
}

export class AccountClassic {
    public id = 0;
    public update_time = new Date(0);

    public constructor(data?: AccountClassicResponse) {
        if (data === undefined) return;

        this.id = data.id;
        this.update_time = new Date(data.update_time);
    }
}

export interface ClassicAccountLinkResponse {
    status: ClassicAccountLinkStatus;
    uid: number | null;
    request_id: number | null;
    expires_at: string | null;
    error_category: string;
}

export class ClassicAccountLink {
    public status: ClassicAccountLinkStatus = 'none';
    public uid?: number;
    public request_id?: number;
    public expires_at?: Date;
    public error_category = '';

    public constructor(data?: ClassicAccountLinkResponse) {
        if (data === undefined) return;

        this.status = data.status;
        this.uid = data.uid === null ? undefined : data.uid;
        this.request_id = data.request_id === null ? undefined : data.request_id;
        this.expires_at = data.expires_at === null ? undefined : new Date(data.expires_at);
        this.error_category = data.error_category;
    }
}
