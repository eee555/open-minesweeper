export interface AccountGitHubResponse {
    id: string;
    parent: number;
}

export class AccountGitHub {
    public id = '';

    public constructor(data?: AccountGitHubResponse) {
        if (data !== undefined) this.id = data.id;
    }
}
