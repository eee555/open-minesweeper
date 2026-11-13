import $axios from '@/http';
import { Dict2FormData as toFormData } from '@/utils/forms';

export type VerificationRequestState = 'none' | 'pending' | 'expired' | 'rejected' | 'approved' | 'verified_root' | 'unverified_root';

export interface VerificationStatus {
    verified: boolean;
    can_submit_replays: boolean;
    has_relation: boolean;
    request_state: VerificationRequestState;
    request_parent_id: number | null;
    created_at: string | null;
    expires_at: string | null;
    cooldown_until: string | null;
    can_request: boolean;
    processing_task_id: string | null;
}

export interface VerificationTaskAccepted {
    task_id: string;
    existing: boolean;
}

export interface VerificationOperationResult {
    status: 'applied' | 'conflict';
    operation: string;
    target_id: number;
    affected: number;
    verified: boolean | null;
    reason: string | null;
}

export interface VerificationTaskResult {
    task_id: string;
    status: string;
    finished_at: string | null;
    result: VerificationOperationResult | null;
    error: string | null;
}

const BASE = '/api/userprofile/verification';
const ADMIN_BASE = '/api/userprofile/admin/verification';

export async function fetchVerificationStatus(): Promise<VerificationStatus> {
    const { data } = await $axios.get<VerificationStatus>(`${BASE}/request`);
    return data;
}

export async function createVerificationRequest(userId: number): Promise<VerificationStatus> {
    const { data } = await $axios.post<VerificationStatus>(`${BASE}/requests`, toFormData({ user_id: userId }));
    return data;
}

export async function approveVerificationRequest(userId: number): Promise<VerificationTaskAccepted> {
    const { data } = await $axios.post<VerificationTaskAccepted>(`${BASE}/requests/${userId}/approve`);
    return data;
}

export async function rejectVerificationRequest(userId: number): Promise<void> {
    await $axios.post(`${BASE}/requests/${userId}/reject`);
}

export async function detachVerification(): Promise<VerificationTaskAccepted> {
    const { data } = await $axios.post<VerificationTaskAccepted>(`${BASE}/detach`);
    return data;
}

export async function fetchVerificationTask(taskId: string): Promise<VerificationTaskResult> {
    const { data } = await $axios.get<VerificationTaskResult>(`${BASE}/tasks/${taskId}`);
    return data;
}

export async function grantVerification(userId: number): Promise<VerificationTaskAccepted> {
    const { data } = await $axios.post<VerificationTaskAccepted>(`${ADMIN_BASE}/grant`, toFormData({ user_id: userId }));
    return data;
}

export async function revokeVerification(userId: number): Promise<VerificationTaskAccepted> {
    const { data } = await $axios.post<VerificationTaskAccepted>(`${ADMIN_BASE}/revoke`, toFormData({ user_id: userId }));
    return data;
}
