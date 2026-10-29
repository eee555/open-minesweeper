export enum LoginStatus {
    // 首次打开页面，还没有做判断，判断是否需要尝试登录，主要是防抖用
    Undefined,
    // 登录成功了
    IsLogin,
    // 未登录状态
    NotLogin,
    // 正在打开弹窗填写登录信息
    Login,
    // 正在打开弹窗填写注册信息
    Register,
    // 正在弹窗上找回密码
    IsRetrieve,
}

export type TaskStatus = '' | 'loading' | 'success' | 'error';

export interface ApiSuccessResponse<T> {
    type: 'success';
    data: T;
}

export interface ApiErrorResponse {
    type: 'error';
    object?: string;
    category?: string;
    msg?: string;
}

export type ApiResponse<T> = ApiSuccessResponse<T> | ApiErrorResponse;

export const DjangoTaskResultStatusOptions = ['READY', 'RUNNING', 'FAILED', 'SUCCESSFUL', 'NULL'] as const;
export type DjangoTaskResultStatus = typeof DjangoTaskResultStatusOptions[number];

export interface GetUserInfoResponse {
    id: number;
    username: string;
    firstname: string;
    lastname: string;
    realname: string;
    is_banned: boolean;
    is_staff: boolean;
    is_superuser?: boolean;
    is_memorial?: boolean;
    country: string;
    signature: string;
    last_change_avatar: string;
    last_change_signature: string;
    left_avatar_n: number;
    left_signature_n: number;
}
