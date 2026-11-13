"""玩家认证业务逻辑：主动认证、管理员设置节点与站长完整批次，均为请求内的同步短事务。

后端只执行站长显式给出的边与节点命令，不计算可达性、替代路径或撤销闭包；
图的一致性由站长在完整批次中负责。
"""

import logging
from typing import Iterator

from django.db import transaction
from django.utils import timezone

from userprofile.models import UserProfile, UserVerifyEdge
from userprofile.utils import has_identity_access
from .cache import (end_maintenance, graph_write_lock, maintenance_is_active, read_maintenance,
                    release_maintenance, require_owned_maintenance, start_maintenance)
from .utils import GRAPH_BATCH_CHUNK_SIZE, MAX_MAINTENANCE_SECONDS, verification_error

logger = logging.getLogger('userprofile')


def _lock_user(user_id: int):
    return UserProfile.objects.select_for_update().filter(pk=user_id).first()


def _chunked(values: list, size: int = GRAPH_BATCH_CHUNK_SIZE) -> Iterator[list]:
    for offset in range(0, len(values), size):
        yield values[offset:offset + size]


def read_verification_status(user: UserProfile) -> dict:
    """只读取本人当前认证、准入与全站维护状态，不在 GET 中写库，不展示认证来源。"""
    return {
        'verified': user.verified,
        'can_submit_replays': has_identity_access(user),
        'can_verify': user.verified,
        'maintenance_active': maintenance_is_active(),
    }


def verify_player(actor_id: int, target_id: int) -> dict:
    """已认证用户主动认证另一名用户：只新增一条边并把目标设为已认证。"""
    with graph_write_lock():
        if maintenance_is_active():
            raise verification_error('maintenance_active')
        with transaction.atomic():
            actor = _lock_user(actor_id)
            if actor is None or not actor.verified:
                raise verification_error('not_verified', status_code=403)
            if actor_id == target_id:
                raise verification_error('self_verify', status_code=400)
            if _lock_user(target_id) is None:
                raise verification_error('not_found', status_code=404)
            _, created = UserVerifyEdge.objects.get_or_create(from_user_id=actor_id, to_user_id=target_id)
            updated = UserProfile.objects.filter(pk=target_id).exclude(verified=True).update(verified=True, date_updated=timezone.now())
    logger.info('User #%s verified #%s: edge_created=%s', actor_id, target_id, created)
    return {'target_id': target_id, 'verified': True, 'edge_created': created, 'nodes_updated': updated}


def set_user_verified(actor_id: int, target_id: int, value: bool) -> dict:
    """管理员显式设置指定用户的 verified，不创建或删除边，不改动其他节点。"""
    with graph_write_lock():
        if maintenance_is_active():
            raise verification_error('maintenance_active')
        with transaction.atomic():
            if _lock_user(target_id) is None:
                raise verification_error('not_found', status_code=404)
            updated = UserProfile.objects.filter(pk=target_id).exclude(verified=value).update(verified=value, date_updated=timezone.now())
    logger.info('User #%s set verified=%s for #%s', actor_id, value, target_id)
    return {'user_id': target_id, 'verified': value, 'nodes_updated': updated}


def maintenance_state(requester_id: int) -> dict:
    state = read_maintenance()
    if state is None:
        return {'active': False, 'owner_id': None, 'expires_at': None, 'owned_by_requester': False}
    return {
        'active': True,
        'owner_id': state['owner_id'],
        'expires_at': state['expires_at'],
        'owned_by_requester': state['owner_id'] == requester_id,
    }


def start_maintenance_session(owner_id: int, duration_seconds: int) -> dict:
    if not 1 <= duration_seconds <= MAX_MAINTENANCE_SECONDS:
        raise verification_error('invalid_duration', status_code=400)
    start_maintenance(owner_id, duration_seconds)
    return maintenance_state(owner_id)


def end_maintenance_session(owner_id: int) -> dict:
    end_maintenance(owner_id)
    return maintenance_state(owner_id)


def read_graph(requester_id: int) -> dict:
    """读取当前全部有向边、已认证节点和会话状态，供站长构造一次完整批次。"""
    edges = [
        {'from_user_id': from_id, 'to_user_id': to_id, 'created_at': created_at}
        for from_id, to_id, created_at in UserVerifyEdge.objects.order_by('id').values_list('from_user_id', 'to_user_id', 'created_at')
    ]
    return {
        'edges': edges,
        'verified_user_ids': list(UserProfile.objects.filter(verified=True).order_by('id').values_list('id', flat=True)),
        'maintenance': maintenance_state(requester_id),
    }


def read_node(user_id: int) -> dict:
    """按用户读取单节点的认证状态、入边与出边，不展示关系历史。"""
    user = UserProfile.objects.filter(pk=user_id).first()
    if user is None:
        raise verification_error('not_found', status_code=404)
    return {
        'user_id': user_id,
        'verified': user.verified,
        'in_edges': list(UserVerifyEdge.objects.filter(to_user_id=user_id).order_by('id').values_list('from_user_id', flat=True)),
        'out_edges': list(UserVerifyEdge.objects.filter(from_user_id=user_id).order_by('id').values_list('to_user_id', flat=True)),
    }


def _normalize_commands(payload: dict) -> dict:
    """只做基础数据校验，不替站长推导节点最终状态或扩展删边范围。"""
    add_edges = [(item['from_user_id'], item['to_user_id']) for item in payload.get('add_edges') or []]
    remove_edges = [(item['from_user_id'], item['to_user_id']) for item in payload.get('remove_edges') or []]
    node_items = [(item['user_id'], item['verified']) for item in payload.get('set_verified') or []]

    for from_id, to_id in [*add_edges, *remove_edges]:
        if from_id == to_id:
            raise verification_error('self_edge', status_code=400)
    add_set, remove_set = set(add_edges), set(remove_edges)
    if len(add_set) != len(add_edges) or len(remove_set) != len(remove_edges):
        raise verification_error('duplicate_input', status_code=400)
    if add_set & remove_set:
        raise verification_error('conflicting_edge', status_code=400)

    nodes = {}
    for user_id, value in node_items:
        if user_id in nodes:
            raise verification_error('duplicate_input' if nodes[user_id] == value else 'conflicting_node', status_code=400)
        nodes[user_id] = value

    referenced = set(nodes)
    for from_id, to_id in [*add_edges, *remove_edges]:
        referenced.update((from_id, to_id))
    existing = set()
    for user_ids in _chunked(sorted(referenced)):
        existing.update(UserProfile.objects.filter(pk__in=user_ids).values_list('id', flat=True))
    if referenced - existing:
        raise verification_error('not_found', status_code=404)
    return {'add_edges': sorted(add_set), 'remove_edges': sorted(remove_set), 'set_verified': nodes}


def submit_graph_update(owner_id: int, payload: dict) -> dict:
    """站长在一个数据库事务中提交完整批次；任一写入失败整体回滚，不留下半生效状态。"""
    commands = _normalize_commands(payload)
    add_edges, remove_edges, nodes = commands['add_edges'], commands['remove_edges'], commands['set_verified']
    with graph_write_lock():
        require_owned_maintenance(owner_id)
        with transaction.atomic():
            affected = set(nodes)
            for from_id, to_id in [*add_edges, *remove_edges]:
                affected.update((from_id, to_id))
            # 固定顺序锁定受影响节点，避免不同批次之间形成死锁。
            for user_ids in _chunked(sorted(affected)):
                list(UserProfile.objects.select_for_update().filter(pk__in=user_ids).order_by('pk'))

            # 一次查出相关边，新增去重与删除都据此决定；SQL 次数只按分块数增长，不按命令数逐条增长。
            from_ids = sorted({from_id for from_id, _ in [*add_edges, *remove_edges]})
            existing_edges = []
            for source_ids in _chunked(from_ids):
                existing_edges.extend(UserVerifyEdge.objects.filter(from_user_id__in=source_ids).values_list('pk', 'from_user_id', 'to_user_id'))
            existing_pairs = {(from_id, to_id) for _, from_id, to_id in existing_edges}
            remove_set = set(remove_edges)
            remove_pks = [pk for pk, from_id, to_id in existing_edges if (from_id, to_id) in remove_set]
            to_create = [UserVerifyEdge(from_user_id=from_id, to_user_id=to_id) for from_id, to_id in add_edges if (from_id, to_id) not in existing_pairs]

            UserVerifyEdge.objects.bulk_create(to_create, ignore_conflicts=True, batch_size=GRAPH_BATCH_CHUNK_SIZE)
            for pks in _chunked(remove_pks):
                UserVerifyEdge.objects.filter(pk__in=pks).delete()

            updated = 0
            now = timezone.now()
            for value in (True, False):
                for user_ids in _chunked([user_id for user_id, target in nodes.items() if target == value]):
                    updated += UserProfile.objects.filter(pk__in=user_ids).exclude(verified=value).update(verified=value, date_updated=now)
        release_maintenance()
    result = {'added_edges': len(to_create), 'removed_edges': len(remove_pks), 'updated_nodes': updated}
    logger.info('Verification graph batch by #%s committed: %s', owner_id, result)
    return result
