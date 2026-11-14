import $axios from '@/http';

export interface VerificationStatus {
    verified: boolean;
    can_verify: boolean;
    maintenance_active: boolean;
}

export interface VerificationActionResult {
    target_id: number;
    verified: boolean;
    edge_created: boolean;
    nodes_updated: number;
}

export interface VerificationEdge {
    from_user_id: number;
    to_user_id: number;
    created_at: string;
}

export interface MaintenanceState {
    active: boolean;
    owner_id: number | null;
    expires_at: string | null;
    owned_by_requester: boolean;
}

export interface VerificationGraph {
    edges: VerificationEdge[];
    verified_user_ids: number[];
    maintenance: MaintenanceState;
}

export interface VerificationNode {
    user_id: number;
    verified: boolean;
    in_edges: number[];
    out_edges: number[];
}

export interface GraphEdgeCommand {
    from_user_id: number;
    to_user_id: number;
}

export interface GraphNodeCommand {
    user_id: number;
    verified: boolean;
}

export interface GraphUpdateCommand {
    add_edges: GraphEdgeCommand[];
    remove_edges: GraphEdgeCommand[];
    set_verified: GraphNodeCommand[];
}

export interface GraphUpdateResult {
    added_edges: number;
    removed_edges: number;
    updated_nodes: number;
}

const BASE = '/api/userprofile/verification';
const ADMIN_BASE = '/api/userprofile/admin/verification';
const JSON_CONFIG = { headers: { 'Content-Type': 'application/json' } };

export async function fetchVerificationStatus(): Promise<VerificationStatus> {
    const { data } = await $axios.get<VerificationStatus>(`${BASE}/status`);
    return data;
}

export async function verifyPlayer(userId: number): Promise<VerificationActionResult> {
    const { data } = await $axios.post<VerificationActionResult>(`${BASE}/verify`, { user_id: userId }, JSON_CONFIG);
    return data;
}

export async function fetchVerificationGraph(): Promise<VerificationGraph> {
    const { data } = await $axios.get<VerificationGraph>(`${ADMIN_BASE}/graph`);
    return data;
}

export async function fetchVerificationNode(userId: number): Promise<VerificationNode> {
    const { data } = await $axios.get<VerificationNode>(`${ADMIN_BASE}/graph/${userId}`);
    return data;
}

export async function startVerificationMaintenance(durationSeconds: number): Promise<MaintenanceState> {
    const { data } = await $axios.post<MaintenanceState>(`${ADMIN_BASE}/maintenance`, { duration_seconds: durationSeconds }, JSON_CONFIG);
    return data;
}

export async function endVerificationMaintenance(): Promise<void> {
    await $axios.delete(`${ADMIN_BASE}/maintenance`);
}

export async function submitVerificationGraphUpdate(command: GraphUpdateCommand): Promise<GraphUpdateResult> {
    const { data } = await $axios.post<GraphUpdateResult>(`${ADMIN_BASE}/graph-update`, command, JSON_CONFIG);
    return data;
}
