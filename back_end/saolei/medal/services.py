from django.db import transaction
from django.db.models import F, Max, Min, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accountlink.models import AccountLinkQueue, Platform
from config.text_choices import Medal_TextChoices, MS_TextChoices
from userprofile.models import UserProfile
from videomanager.models import STNB_COEFFICIENTS, VideoModel
from .cache import invalidate_catalog, read_catalog, read_player_states, write_catalog, write_player_states
from .models import MedalDefinition, MedalGrant, MedalOverride, MedalOverrideLog, MedalPins, MedalScan, PlayerMedalSummary, PlayerProgress
from .utils import basic_definitions, BVS_SCALE, MAX_PINS, next_threshold, NOVICE_LEVELS, NOVICE_LEVELS_NF, NOVICE_MODES, NOVICE_REALNAME, NOVICE_REVIEW, NOVICE_SAOLEI, open_modes, reached_asc_stage, reached_desc_stage, scale_units, SHAREHOLDER_CODE, SHAREHOLDER_THRESHOLDS, STANDARD_LEVELS, threshold_index, THRP_SCALE, VIDEO_ONCE_CODES


class MedalError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class _Unset:
    pass


UNSET = _Unset()


def definition_payload(definition):
    return {
        'code': definition.code,
        'series': definition.series,
        'subseries': definition.subseries,
        'kind': definition.kind,
        'metric': definition.metric,
        'direction': definition.direction,
        'level': definition.level,
        'style': definition.style,
        'thresholds': list(definition.thresholds or []),
        'hidden': definition.hidden,
        'score_by_stage': list(definition.score_by_stage or []),
        'annotation': definition.annotation,
    }


def ensure_shareholder_definition():
    """补上原始股东这一行。已有的阈值和开关保持不动，运营改过的刻度不会被写回。"""
    definition, _created = MedalDefinition.objects.get_or_create(
        code=SHAREHOLDER_CODE,
        defaults={
            'series': Medal_TextChoices.Series.SHAREHOLDER, 'kind': Medal_TextChoices.Kind.MIN_VIDEO_ID, 'metric': 'video_id', 'direction': Medal_TextChoices.Direction.DESC,
            'thresholds': list(SHAREHOLDER_THRESHOLDS), 'score_by_stage': [], 'active': True,
        },
    )
    return definition


def ensure_basic_definitions():
    """补上新手和能力定义，已有定义保持不动。"""
    specs = basic_definitions()
    codes = [item['code'] for item in specs]
    existing = set(MedalDefinition.objects.filter(code__in=codes).values_list('code', flat=True))
    missing = [item for item in specs if item['code'] not in existing]
    created = MedalDefinition.objects.bulk_create([MedalDefinition(**item) for item in missing]) if missing else []
    if created:
        invalidate_catalog()
    return created


def active_definitions():
    cached = read_catalog()
    if cached is not None:
        return cached
    ensure_shareholder_definition()
    ensure_basic_definitions()
    rows = [definition_payload(item) for item in MedalDefinition.objects.filter(active=True).order_by('series', 'subseries', 'code')]
    write_catalog(rows)
    return rows


def _public_definition(row, include_annotation):
    payload = {
        'code': row['code'], 'series': row['series'], 'subseries': row['subseries'], 'kind': row['kind'],
        'metric': row['metric'], 'direction': row['direction'], 'level': row['level'], 'style': row['style'],
        'thresholds': row['thresholds'], 'hidden': row['hidden'], 'annotation': row['annotation'] if include_annotation else '',
    }
    return payload


def catalog_for(user):
    rows = active_definitions()
    unlocked = set()
    if getattr(user, 'is_authenticated', False):
        hidden_codes = [row['code'] for row in rows if row['hidden']]
        if hidden_codes:
            unlocked = set(MedalGrant.objects.filter(user=user, revoked_at__isnull=True, definition_code__in=hidden_codes).values_list('definition_code', flat=True))
    visible = []
    for row in rows:
        if row['hidden'] and row['code'] not in unlocked:
            continue
        visible.append(_public_definition(row, include_annotation=row['hidden']))
    return visible


def _evidence_id(video, participant, evidence):
    if video is not None and not isinstance(video, _Unset):
        return getattr(video, 'id', video)
    if isinstance(evidence, dict) and evidence.get('video_id') is not None:
        return evidence.get('video_id')
    if participant is not None and not isinstance(participant, _Unset):
        return getattr(participant, 'id', None)
    return None


def _append_log(grant, stage, at, evidence_id):
    log = list(grant.stage_log or [])
    if log and log[-1].get('stage') == stage:
        return log
    log.append({'stage': stage, 'at': at.isoformat(), 'evidence_id': evidence_id})
    return log


class _EvaluationState:
    """一次评估共用已读状态，进度只在最后集中写入有变化的行。"""

    def __init__(self, user):
        self.definitions = {row.code: row for row in MedalDefinition.objects.filter(active=True)}
        self.progress = {row.code: row for row in PlayerProgress.objects.filter(user=user)}
        self.all_grants = {(row.definition_code, row.scope_key): row for row in MedalGrant.objects.filter(user=user).select_related('video', 'participant')}
        self.grants = {row.definition_code: row for row in self.all_grants.values() if not row.scope_key}
        self.overrides = {(row.definition_code, row.scope_key): row for row in MedalOverride.objects.filter(user=user)}
        self.changed = {}
        self.history_dirty = set()

    def definitions_of(self, kind):
        return [row for row in self.definitions.values() if row.kind == kind]

    def flush(self):
        new = [row for row in self.changed.values() if row.pk is None]
        changed = [row for row in self.changed.values() if row.pk is not None]
        if new:
            PlayerProgress.objects.bulk_create(new)
        if changed:
            PlayerProgress.objects.bulk_update(changed, ['definition', 'current_stage', 'current_value', 'extra', 'best_video'])


def _save_progress(user, definition, stage_value, current_value, extra, best_video, state=None):
    # 能力勋章只保留自然档位，成绩及录像由授予证据提供，不另存一份 PB。
    if definition.kind == Medal_TextChoices.Kind.PB:
        current_value, best_video = None, None
    progress = state.progress.get(definition.code) if state is not None else PlayerProgress.objects.filter(user=user, code=definition.code).first()
    if progress is None:
        progress = PlayerProgress(
            user=user, definition=definition, code=definition.code, current_stage=stage_value,
            current_value=None if current_value is UNSET else current_value,
            extra=None if extra is UNSET else extra,
            best_video=None if best_video is UNSET else best_video,
        )
        if state is None:
            progress.save(update_fields=None)
        else:
            state.progress[definition.code] = progress
            state.changed[definition.code] = progress
        return progress
    values = {'definition_id': definition.pk, 'current_stage': stage_value, 'current_value': current_value, 'extra': extra}
    if best_video is not UNSET:
        values['best_video_id'] = None if best_video is None else best_video.pk
    fields = []
    for field, value in values.items():
        if value is not UNSET and getattr(progress, field) != value:
            setattr(progress, field, value)
            fields.append(field)
    if best_video is not UNSET:
        progress.best_video = best_video
    if fields:
        if state is None:
            progress.save(update_fields=fields)
        else:
            state.changed[definition.code] = progress
    return progress


def _apply_grant_fields(grant, stage, video, participant, evidence, logged_at, append_log, clear_revoke, reset_granted_at=False):
    grant.stage = stage
    fields = ['stage']
    if reset_granted_at:
        grant.granted_at = logged_at
        fields.append('granted_at')
    if video is not UNSET:
        grant.video = video
        fields.append('video')
    if participant is not UNSET:
        grant.participant = participant
        fields.append('participant')
    if evidence is not UNSET:
        grant.evidence = evidence
        fields.append('evidence')
    if append_log:
        grant.stage_log = _append_log(grant, stage, logged_at, _evidence_id(video, participant, grant.evidence))
        fields.append('stage_log')
    if clear_revoke:
        grant.revoked_at = None
        grant.revoke_reason = ''
        fields.extend(['revoked_at', 'revoke_reason'])
    grant.save(update_fields=fields)
    return grant


def write_stage(user, definition, scope_key='', stage=0, current_value=UNSET, granted_at=None, video=UNSET, participant=UNSET, evidence=UNSET, best_video=UNSET, extra=UNSET, keep_evidence=True, state=None):
    # 整轮评估已经持有事务与玩家锁，无需为每枚勋章创建数据库保存点。
    with transaction.atomic(savepoint=state is None):
        if state is None:
            user = _lock_summary_user(user.pk)
            if user is None:
                raise MedalError('user')
        grant = _write_stage(user, definition, scope_key, stage, current_value, granted_at, video, participant, evidence, best_video, extra, keep_evidence, state)
        if state is None:
            _publish_summary(user)
        return grant


def _write_stage(user, definition, scope_key, stage, current_value, granted_at, video, participant, evidence, best_video, extra, keep_evidence, state):
    """按当前阶段改写同一枚授予。0 表示一档都不够，撤销这一行。人工纪念不在这里撤销。"""
    new_rank = threshold_index(definition.thresholds, stage)
    if definition.kind == Medal_TextChoices.Kind.MANUAL and new_rank < 0:
        return MedalGrant.objects.filter(user=user, definition_code=definition.code, scope_key=scope_key).first()

    stage_value = stage if new_rank >= 0 else 0
    _save_progress(user, definition, stage_value, current_value, extra, best_video, state)
    grant = state.all_grants.get((definition.code, scope_key)) if state is not None else MedalGrant.objects.select_for_update().filter(user=user, definition_code=definition.code, scope_key=scope_key).first()
    override = state.overrides.get((definition.code, scope_key)) if state is not None else MedalOverride.objects.filter(user=user, definition_code=definition.code, scope_key=scope_key).first()
    if override is not None:
        return grant
    logged_at = granted_at or timezone.now()

    if new_rank < 0:
        if grant is not None and grant.revoked_at is None:
            grant.revoked_at = timezone.now()
            grant.revoke_reason = 'stage'
            grant.save(update_fields=['revoked_at', 'revoke_reason'])
        return grant

    if grant is None:
        evidence_value = {} if evidence is UNSET else evidence
        grant = MedalGrant.objects.create(
            user=user, definition_code=definition.code, stage=stage, scope_key=scope_key,
            stage_log=[{'stage': stage, 'at': logged_at.isoformat(), 'evidence_id': _evidence_id(video, participant, evidence_value)}],
            video=None if video is UNSET else video, participant=None if participant is UNSET else participant,
            evidence=evidence_value, granted_at=logged_at,
        )
        if state is not None:
            state.all_grants[(definition.code, scope_key)] = grant
            state.history_dirty.add(definition.code)
            if not scope_key:
                state.grants[definition.code] = grant
        return grant

    old_rank = threshold_index(definition.thresholds, grant.stage)
    if grant.revoked_at is not None or new_rank != old_rank or not keep_evidence:
        if state is not None:
            state.history_dirty.add(definition.code)
        return _apply_grant_fields(
            grant, stage, video, participant, evidence, logged_at,
            append_log=grant.revoked_at is not None or new_rank != old_rank,
            clear_revoke=grant.revoked_at is not None,
            reset_granted_at=isinstance(grant.evidence, dict) and grant.evidence.get('override') is True,
        )
    return grant


def _summary_grant(grant):
    evidence = grant.evidence if isinstance(grant.evidence, dict) else {}
    rank = evidence.get('rank') if isinstance(evidence.get('rank'), int) else None
    tournament_id = None
    if grant.participant_id:
        tournament_id = grant.participant.tournament_id
    elif isinstance(evidence.get('tournament_id'), int):
        tournament_id = evidence['tournament_id']
    return {
        'id': grant.id, 'code': grant.definition_code, 'stage': grant.stage, 'scope_key': grant.scope_key,
        'granted_at': grant.granted_at.isoformat(), 'video_id': grant.video_id, 'tournament_id': tournament_id, 'rank': rank,
    }


def _medal_item(definition, grant, progress):
    thresholds = definition['thresholds']
    stage = grant['stage'] if grant is not None else None
    value = progress if grant is None or grant['scope_key'] == '' else None
    if definition['kind'] == Medal_TextChoices.Kind.PB:
        value = None
    index = threshold_index(thresholds, stage) if stage else -1
    scores = definition['score_by_stage']
    score = 0
    if grant is not None and not definition['hidden'] and 0 <= index < len(scores):
        score = int(scores[index])
    return {
        'code': definition['code'], 'series': definition['series'], 'subseries': definition['subseries'],
        'kind': definition['kind'], 'stage': stage, 'stage_count': len(thresholds), 'direction': definition['direction'],
        'current_value': value, 'next_threshold': next_threshold(thresholds, stage or 0),
        'granted_at': grant['granted_at'] if grant is not None else None,
        'video_id': grant['video_id'] if grant is not None else None,
        'tournament_id': grant['tournament_id'] if grant is not None else None, 'rank': grant['rank'] if grant is not None else None,
        'hidden': definition['hidden'], 'annotation': definition['annotation'] if definition['hidden'] and grant is not None else '',
        'score': score, 'grant_id': grant['id'] if grant is not None else None,
        'scope_key': grant['scope_key'] if grant is not None else '', 'thresholds': thresholds,
    }


def _lock_summary_user(user_id):
    return UserProfile.objects.select_for_update().select_related('medal_summary', 'medal_pins', 'medal_scan').filter(pk=user_id).first()


def _unix_seconds(value):
    if value is None:
        return None
    return int(value.timestamp())


def _set_from_extra(extra, key):
    if not isinstance(extra, dict):
        return []
    values = extra.get(key)
    if not isinstance(values, list):
        return []
    return [str(item) for item in values]


def _display_state(data):
    """名字悬停只按佩戴顺序返回已授予短记录；没佩戴则为空。"""
    by_id = {}
    for row in data.get('grants') or []:
        grant_id = row.get('id')
        if not isinstance(grant_id, int) or not row.get('stage'):
            continue
        by_id[grant_id] = {
            'code': row['code'], 'stage': row['stage'], 'timestamp': _unix_seconds(parse_datetime(row['granted_at'])),
            'scope': row['scope_key'], 'tournament': row['tournament_id'], 'rank': row['rank'],
        }
    grants = []
    seen = set()
    for pin_id in data.get('pin_ids') or []:
        if pin_id in seen or len(grants) >= MAX_PINS:
            continue
        row = by_id.get(pin_id)
        if row is None:
            continue
        seen.add(pin_id)
        grants.append(row)
    return {'grants': grants}


@transaction.atomic
def _flush_player_states(user_ids):
    """缓存写入共用玩家锁并读取最新摘要，旧回调和冷缓存回填不能覆盖新结果。"""
    users = list(UserProfile.objects.select_for_update().select_related('medal_summary', 'medal_scan', 'medal_pins').filter(pk__in=user_ids).order_by('pk'))
    scanned = [user for user in users if getattr(user, 'medal_scan', None) is not None]
    missing = [user.pk for user in scanned if getattr(user, 'medal_summary', None) is None]
    grants = {}
    if missing:
        # 证据删除或旧数据没有摘要时只读勋章，不回扫录像，也不逐个玩家查库。
        for grant in MedalGrant.objects.filter(user_id__in=missing, revoked_at__isnull=True).select_related('participant').order_by('scope_key', 'id'):
            grants.setdefault(grant.user_id, []).append(_summary_grant(grant))
    stored = {}
    for user in scanned:
        summary = getattr(user, 'medal_summary', None)
        if summary is not None:
            data = summary.data
        else:
            pins = getattr(user, 'medal_pins', None)
            pin_ids = pins.grant_ids if pins is not None and isinstance(pins.grant_ids, list) else []
            data = {'grants': grants.get(user.pk, []), 'pin_ids': pin_ids}
        stored[user.pk] = _display_state(data)
    write_player_states(stored)
    return stored


def _schedule_player_state(user):
    if getattr(user, 'medal_scan', None) is not None:
        user_id = user.pk
        transaction.on_commit(lambda user_id=user_id: _flush_player_states([user_id]), robust=True)


def _publish_summary(user, state=None):
    """调用者持有玩家锁；只保存玩家数据，定义、可见性和计分仍使用当前图鉴。"""
    if state is None:
        grants = MedalGrant.objects.filter(user=user, revoked_at__isnull=True).select_related('participant')
        progress = dict(PlayerProgress.objects.filter(user=user).values_list('code', 'current_value'))
    else:
        grants = [grant for grant in state.all_grants.values() if grant.revoked_at is None]
        progress = {code: row.current_value for code, row in state.progress.items()}
    pins = getattr(user, 'medal_pins', None)
    data = {
        'scan_pending': getattr(user, 'medal_scan', None) is None,
        'grants': [_summary_grant(grant) for grant in sorted(grants, key=lambda grant: (grant.scope_key, grant.id))],
        'progress': progress,
        'pin_ids': pins.grant_ids if pins is not None and isinstance(pins.grant_ids, list) else [],
    }
    summary = getattr(user, 'medal_summary', None)
    display_changed = summary is None or summary.data.get('scan_pending') != data['scan_pending'] or _display_state(summary.data) != _display_state(data)
    if summary is None:
        user.medal_summary = PlayerMedalSummary.objects.create(user=user, data=data)
    elif summary.data != data:
        summary.data = data
        summary.save(update_fields=['data'])
    if display_changed:
        _schedule_player_state(user)
    return data


def _read_summary(user_id):
    row = UserProfile.objects.filter(pk=user_id).values('id', 'medal_summary__data').first()
    if row is None:
        raise MedalError('user')
    if row['medal_summary__data'] is not None:
        return row['medal_summary__data']
    # 旧玩家首次读取时从现有勋章表补齐，不重新聚合录像。与写入使用同一把玩家锁。
    with transaction.atomic():
        user = _lock_summary_user(user_id)
        if user is None:
            raise MedalError('user')
        existing = getattr(user, 'medal_summary', None)
        return existing.data if existing is not None else _publish_summary(user)


def _require_user(user_id):
    if not UserProfile.objects.filter(pk=user_id).exists():
        raise MedalError('user')


def player_summary(user_id):
    data = _read_summary(user_id)
    definitions = active_definitions()
    grants_by_code = {}
    for grant in data['grants']:
        grants_by_code.setdefault(grant['code'], []).append(grant)
    progress_by_code = data['progress']
    series = []
    index_by_name = {}
    items_by_grant = {}

    def add(item):
        name = item['series']
        if name not in index_by_name:
            index_by_name[name] = len(series)
            series.append({'series': name, 'items': []})
        series[index_by_name[name]]['items'].append(item)
        if item['grant_id'] is not None:
            items_by_grant[item['grant_id']] = item

    for definition in definitions:
        matching = grants_by_code.get(definition['code'], [])
        if definition['hidden'] and not matching:
            continue
        progress = progress_by_code.get(definition['code'])
        if matching:
            for grant in matching:
                add(_medal_item(definition, grant, progress))
        else:
            add(_medal_item(definition, None, progress))

    stored = [item for item in data['pin_ids'] if isinstance(item, int)]
    pin_items = [items_by_grant[item] for item in stored if item in items_by_grant][:MAX_PINS]
    return {
        'scan_pending': data['scan_pending'],
        'score': sum(item['score'] for group in series for item in group['items']),
        'max_pins': MAX_PINS,
        'pin_ids': [item['grant_id'] for item in pin_items],
        'pins': pin_items,
        'series': series,
    }


def _public_state_grants(payload):
    if not payload:
        return []
    rows = []
    for item in payload.get('grants') or []:
        if item.get('locked') or not item.get('stage'):
            continue
        rows.append({
            'code': item['code'], 'stage': item['stage'], 'timestamp': item.get('timestamp'),
            'scope': item.get('scope') or '', 'tournament': item.get('tournament'), 'rank': item.get('rank'),
        })
    return rows


def player_states(user_ids):
    """Redis 命中时不查库；缺键批量读最新摘要，未扫描玩家仍返回空列表。"""
    stored = read_player_states(user_ids)
    missing = [user_id for user_id in user_ids if user_id not in stored]
    if missing:
        stored.update(_flush_player_states(missing))
    return [{'user_id': user_id, 'grants': _public_state_grants(stored.get(user_id))} for user_id in user_ids]


def list_grants(user_id, page, page_size):
    _require_user(user_id)
    definitions = {row['code']: row for row in active_definitions()}
    queryset = MedalGrant.objects.filter(user_id=user_id, revoked_at__isnull=True, definition_code__in=list(definitions)).select_related('participant').order_by('-granted_at', '-id')
    count = queryset.count()
    start = (page - 1) * page_size
    rows = list(queryset[start:start + page_size])
    progress_by_code = dict(PlayerProgress.objects.filter(user_id=user_id, code__in=[row.definition_code for row in rows]).values_list('code', 'current_value'))
    items = [_medal_item(definitions[row.definition_code], _summary_grant(row), progress_by_code.get(row.definition_code)) for row in rows]
    return {'count': count, 'page': page, 'page_size': page_size, 'items': items}


@transaction.atomic
def replace_pins(user, grant_ids):
    if len(grant_ids) > MAX_PINS:
        raise MedalError('too_many')
    if len(set(grant_ids)) != len(grant_ids):
        raise MedalError('duplicate')
    user = _lock_summary_user(user.pk)
    if user is None:
        raise MedalError('user')
    owned = set(MedalGrant.objects.filter(user=user, revoked_at__isnull=True, id__in=grant_ids).values_list('id', flat=True))
    if owned != set(grant_ids):
        raise MedalError('unavailable')
    user.medal_pins, _created = MedalPins.objects.update_or_create(user=user, defaults={'grant_ids': list(grant_ids)})
    _publish_summary(user)
    return list(grant_ids)


def grant_manual(actor, code, user_id, reason, granted_at, stage=None, scope_key=''):
    definition = MedalDefinition.objects.filter(pk=code).first()
    if definition is None:
        raise MedalError('definition')
    if stage is None and definition.kind == Medal_TextChoices.Kind.MANUAL:
        stage = definition.thresholds[0] if definition.thresholds else 1
    return set_player_override(
        actor, user_id, code, scope_key, 'grant', reason, stage=stage, granted_at=granted_at,
    )


def _evaluate_locked(user):
    """调用者已持有玩家锁。跑完才记下 MedalScan，提交后再写 Redis。"""
    ensure_basic_definitions()
    ensure_shareholder_definition()
    state = _EvaluationState(user)
    evaluate_min_video_id(user, state)
    evaluate_once(user, state)
    evaluate_pb(user, state)
    evaluate_composite(user, state)
    _refresh_video_history(user, state)
    state.flush()
    user.medal_scan, _created = MedalScan.objects.get_or_create(user=user, defaults={'scanned_at': timezone.now()})
    _publish_summary(user, state)


@transaction.atomic
def evaluate_player(user_id):
    """重算该玩家已经接上的勋章。用户不存在时直接返回。跑完才记下 MedalScan。"""
    user = _lock_summary_user(user_id)
    if user is None:
        return
    _evaluate_locked(user)


def evaluate_min_video_id(user, state=None):
    """按该玩家仍在库里的最小录像 id 改写原始股东。不看出审、模式和难度。"""
    definition = state.definitions.get(SHAREHOLDER_CODE) if state is not None else ensure_shareholder_definition()
    if definition is None or not definition.active:
        return None
    video = VideoModel.objects.filter(player_id=user.id).order_by('id').first()
    if video is None:
        return write_stage(user, definition, stage=0, current_value=None, best_video=None, state=state)
    stage = reached_desc_stage(definition.thresholds, video.id)
    existing = state.grants.get(definition.code) if state is not None else MedalGrant.objects.filter(user=user, definition_code=definition.code, scope_key='').select_related('video').first()
    evidence_remains = (
        existing is not None and existing.revoked_at is None and existing.stage == stage and existing.video_id is not None
        and existing.video.player_id == user.id
    )
    return write_stage(
        user, definition, stage=stage, current_value=video.id, granted_at=video.upload_time,
        video=video, best_video=video, evidence={'video_id': video.id}, keep_evidence=evidence_remains, state=state,
    )


def _official_videos(user):
    return VideoModel.objects.filter(player_id=user.id, state=MS_TextChoices.State.OFFICIAL)


def _style_key(definition):
    if definition.style in (Medal_TextChoices.Style.NF, Medal_TextChoices.Style.FL):
        return definition.style
    return 'any'


def _pb_queryset(user, level):
    return VideoModel.objects.filter(
        player_id=user.id, state=MS_TextChoices.State.OFFICIAL, mode=MS_TextChoices.Mode.STD,
        level=level, ongoing_tournament=False,
    )


def _thrp_filter(style):
    base = Q(ce__gt=0, bv__isnull=False)
    if style == Medal_TextChoices.Style.NF:
        return base & Q(right_ce=0, ce__gte=F('bv'))
    if style == Medal_TextChoices.Style.FL:
        return base & Q(right_ce__gt=0)
    return base


def _qualified(user, definition):
    queryset = _pb_queryset(user, definition.level)
    style = _style_key(definition)
    if definition.metric == 'thrp':
        return queryset.filter(_thrp_filter(style))
    if style == Medal_TextChoices.Style.NF:
        return queryset.filter(right_ce=0)
    if style == Medal_TextChoices.Style.FL:
        return queryset.filter(right_ce__gt=0)
    return queryset


def _video_qualifies(video, definition, user_id):
    if video is None or video.player_id != user_id or video.ongoing_tournament:
        return False
    if video.state != MS_TextChoices.State.OFFICIAL or video.mode != MS_TextChoices.Mode.STD or video.level != definition.level:
        return False
    style = _style_key(definition)
    if style == Medal_TextChoices.Style.NF and video.right_ce != 0:
        return False
    if style == Medal_TextChoices.Style.FL and (video.right_ce is None or video.right_ce <= 0):
        return False
    if definition.metric == 'timems':
        return video.timems is not None
    if definition.metric == 'bvs':
        return video.bvs is not None
    if definition.metric == 'stnb':
        return video.iqg is not None and definition.level in STNB_COEFFICIENTS
    if definition.metric != 'thrp':
        return False
    if video.thrp is None or video.ce is None or video.bv is None or video.ce <= 0:
        return False
    if style == Medal_TextChoices.Style.NF and video.ce < video.bv:
        return False
    return True


def _raw_value(video, definition):
    if video is None:
        return None
    if definition.metric == 'timems':
        return video.timems
    if definition.metric == 'bvs':
        return video.bvs
    if definition.metric == 'stnb':
        coefficient = STNB_COEFFICIENTS.get(definition.level)
        if coefficient is None or video.iqg is None:
            return None
        return coefficient * video.iqg
    if definition.metric == 'thrp':
        return video.thrp
    return None


def _units_of(definition, raw):
    if raw is None:
        return None
    if definition.metric == 'timems':
        return int(raw)
    if definition.metric == 'stnb':
        return scale_units(raw, 1)
    if definition.metric == 'bvs':
        return scale_units(raw, BVS_SCALE)
    if definition.metric == 'thrp':
        return scale_units(raw, THRP_SCALE)
    return None


def _stage_of(definition, raw):
    if raw is None:
        return 0
    if definition.metric == 'timems':
        return reached_desc_stage(definition.thresholds, raw)
    if definition.metric == 'stnb':
        return reached_asc_stage(definition.thresholds, raw)
    return reached_asc_stage(definition.thresholds, _units_of(definition, raw))


def _meets_stage(definition, raw, stage):
    if raw is None or not stage:
        return False
    if definition.metric == 'timems':
        return raw < stage
    if definition.metric == 'stnb':
        return raw >= stage
    units = _units_of(definition, raw)
    return units is not None and units >= stage


def _aggregate_level(user, level):
    queryset = _pb_queryset(user, level)
    nf = Q(right_ce=0)
    return queryset.aggregate(
        time_any=Min('timems'), bvs_any=Max('bvs'), iqg_any=Max('iqg'),
        time_nf=Min('timems', filter=nf), bvs_nf=Max('bvs', filter=nf), iqg_nf=Max('iqg', filter=nf),
        thrp_nf=Max('thrp', filter=_thrp_filter(Medal_TextChoices.Style.NF)), thrp_fl=Max('thrp', filter=_thrp_filter(Medal_TextChoices.Style.FL)),
    )


def _aggregate_raw(stats, definition):
    style = _style_key(definition)
    metric = definition.metric
    if metric == 'timems':
        return stats['time_nf'] if style == Medal_TextChoices.Style.NF else stats['time_any']
    if metric == 'bvs':
        return stats['bvs_nf'] if style == Medal_TextChoices.Style.NF else stats['bvs_any']
    if metric == 'stnb':
        iqg = stats['iqg_nf'] if style == Medal_TextChoices.Style.NF else stats['iqg_any']
        coefficient = STNB_COEFFICIENTS.get(definition.level)
        if iqg is None or coefficient is None:
            return None
        return coefficient * iqg
    if metric == 'thrp':
        return stats['thrp_nf'] if style == Medal_TextChoices.Style.NF else stats['thrp_fl'] if style == Medal_TextChoices.Style.FL else None
    return None


def _earliest_for_stage(user, definition, stage):
    queryset = _qualified(user, definition)
    if definition.metric == 'timems':
        queryset = queryset.filter(timems__lt=stage)
    elif definition.metric == 'stnb':
        coefficient = STNB_COEFFICIENTS.get(definition.level)
        if not coefficient:
            return None
        queryset = queryset.filter(iqg__gte=stage / coefficient)
    elif definition.metric == 'bvs':
        queryset = queryset.filter(bvs__gte=(stage - 0.5) / BVS_SCALE)
    else:
        queryset = queryset.filter(thrp__gte=(stage - 0.5) / THRP_SCALE)
    return queryset.order_by('upload_time', 'id').first()


def _evidence_stands(grant, definition, stage, user_id):
    if grant is None or grant.revoked_at is not None or grant.stage != stage or grant.video_id is None:
        return False
    video = grant.video
    raw = _raw_value(video, definition)
    return _video_qualifies(video, definition, user_id) and _meets_stage(definition, raw, stage)


def _apply_pb(user, definition, stats, progress, grant, state=None, overridden=False):
    stage = _stage_of(definition, _aggregate_raw(stats, definition))
    if overridden:
        if progress is not None or stage > 0:
            _save_progress(user, definition, stage, None, UNSET, None, state)
        return grant
    if stage <= 0:
        if progress is None and (grant is None or grant.revoked_at is not None):
            return grant
        return write_stage(user, definition, stage=0, state=state)
    if _evidence_stands(grant, definition, stage, user.id):
        return write_stage(user, definition, stage=stage, keep_evidence=True, state=state)
    earliest = _earliest_for_stage(user, definition, stage)
    return write_stage(
        user, definition, stage=stage, video=earliest,
        granted_at=None if earliest is None else earliest.upload_time, evidence={'video_id': None if earliest is None else earliest.id},
        keep_evidence=False, state=state,
    )


def evaluate_pb(user, state=None, levels=None):
    """全量或失效重算时按难度聚合判定档位，聚合值只用于本次计算，不保存最佳成绩及录像。"""
    definitions = [row for row in state.definitions_of(Medal_TextChoices.Kind.PB) if row.metric in ('timems', 'bvs', 'stnb', 'thrp') and row.level in STANDARD_LEVELS] if state is not None else list(MedalDefinition.objects.filter(active=True, kind=Medal_TextChoices.Kind.PB, metric__in=['timems', 'bvs', 'stnb', 'thrp'], level__in=STANDARD_LEVELS))
    if not definitions:
        return
    codes = [item.code for item in definitions]
    progress = state.progress if state is not None else {row.code: row for row in PlayerProgress.objects.filter(user=user, code__in=codes)}
    grants = state.grants if state is not None else {row.definition_code: row for row in MedalGrant.objects.filter(user=user, definition_code__in=codes, scope_key='').select_related('video')}
    overrides = state.overrides if state is not None else {(row.definition_code, row.scope_key): row for row in MedalOverride.objects.filter(user=user, scope_key='')}
    by_level = {}
    for definition in definitions:
        by_level.setdefault(definition.level, []).append(definition)
    for level, level_definitions in by_level.items():
        if levels is not None and level not in levels:
            continue
        stats = _aggregate_level(user, level)
        for definition in level_definitions:
            _apply_pb(user, definition, stats, progress.get(definition.code), grants.get(definition.code), state, (definition.code, '') in overrides)


def _mode_list(definition):
    stored = definition.scope.get('modes') if isinstance(definition.scope, dict) else None
    if isinstance(stored, list) and stored:
        return [str(item) for item in stored]
    return open_modes()


def _earliest_official(user, **filters):
    return _official_videos(user).filter(**filters).order_by('upload_time', 'id').first()


def _completing_video(videos):
    if not videos:
        return None
    return max(videos, key=lambda video: (video.upload_time, video.id))


def _saolei_platform(definition):
    if isinstance(definition.scope, dict) and definition.scope.get('platform'):
        return definition.scope['platform']
    return Platform.SAOLEI


def _covers(found, needed):
    return set(needed) <= set(found)


def _novice_levels_found(user, *, nf=False):
    queryset = _official_videos(user).filter(level__in=STANDARD_LEVELS)
    if nf:
        queryset = queryset.filter(right_ce=0)
    return sorted({str(level) for level in queryset.values_list('level', flat=True).distinct()})


def _novice_modes_found(user, definition):
    modes = _mode_list(definition)
    found = _official_videos(user).filter(mode__in=modes).values_list('mode', flat=True).distinct()
    return sorted({str(mode) for mode in found})


def _novice_progress_extra(user, definition):
    if definition.code == NOVICE_LEVELS:
        levels = _novice_levels_found(user)
        return {'levels': levels} if levels else None
    if definition.code == NOVICE_LEVELS_NF:
        levels = _novice_levels_found(user, nf=True)
        return {'levels': levels} if levels else None
    if definition.code == NOVICE_MODES:
        modes = _novice_modes_found(user, definition)
        return {'modes': modes} if modes else None
    return None


def _once_satisfied(user, definition):
    if definition.code == NOVICE_REALNAME:
        return user.has_realname()
    if definition.code == NOVICE_REVIEW:
        return _official_videos(user).exists()
    if definition.code == NOVICE_LEVELS:
        return _covers(_novice_levels_found(user), STANDARD_LEVELS)
    if definition.code == NOVICE_LEVELS_NF:
        return _covers(_novice_levels_found(user, nf=True), STANDARD_LEVELS)
    if definition.code == NOVICE_MODES:
        return _covers(_novice_modes_found(user, definition), _mode_list(definition))
    if definition.code == NOVICE_SAOLEI:
        return AccountLinkQueue.objects.filter(userprofile=user, platform=_saolei_platform(definition), verified=True).exists()
    return False


def _once_video(user, definition):
    if definition.code == NOVICE_REVIEW:
        return _earliest_official(user)
    if definition.code == NOVICE_LEVELS:
        return _completing_video([_earliest_official(user, level=level) for level in STANDARD_LEVELS])
    if definition.code == NOVICE_LEVELS_NF:
        return _completing_video([_earliest_official(user, level=level, right_ce=0) for level in STANDARD_LEVELS])
    if definition.code == NOVICE_MODES:
        return _completing_video([_earliest_official(user, mode=mode) for mode in _mode_list(definition)])
    return None


def _once_evidence_stands(grant, definition):
    if grant is None or grant.revoked_at is not None or grant.stage != 1:
        return False
    if definition.code in (NOVICE_REALNAME, NOVICE_SAOLEI):
        return True
    video = grant.video
    if video is None or video.state != MS_TextChoices.State.OFFICIAL or video.player_id != grant.user_id:
        return False
    if definition.code == NOVICE_LEVELS_NF and video.right_ce != 0:
        return False
    if definition.code == NOVICE_LEVELS and video.level not in STANDARD_LEVELS:
        return False
    if definition.code == NOVICE_MODES and video.mode not in _mode_list(definition):
        return False
    return True


def _write_once(user, definition, met, state=None):
    grant = state.grants.get(definition.code) if state is not None else MedalGrant.objects.filter(user=user, definition_code=definition.code, scope_key='').select_related('video').first()
    if not met:
        extra = _novice_progress_extra(user, definition)
        if grant is None or grant.revoked_at is not None:
            if extra is not None or (state is not None and definition.code in state.progress):
                _save_progress(user, definition, 0, 0, extra, None, state)
            return grant
        return write_stage(user, definition, stage=0, current_value=0, best_video=None, extra=extra, state=state)
    if _once_evidence_stands(grant, definition):
        return write_stage(user, definition, stage=1, current_value=1, keep_evidence=True, extra=None, state=state)
    video = _once_video(user, definition)
    if video is None and definition.code not in (NOVICE_REALNAME, NOVICE_SAOLEI):
        extra = _novice_progress_extra(user, definition)
        if grant is None or grant.revoked_at is not None:
            if extra is not None:
                _save_progress(user, definition, 0, 0, extra, None, state)
            return grant
        return write_stage(user, definition, stage=0, current_value=0, best_video=None, extra=extra, state=state)
    evidence = {} if video is None else {'video_id': video.id}
    return write_stage(
        user, definition, stage=1, current_value=1, video=video, best_video=video,
        granted_at=None if video is None else video.upload_time, evidence=evidence, keep_evidence=False, extra=None, state=state,
    )


def evaluate_once(user, state=None):
    """实名、过审、全级别、全模式，以及扫雷网已验证。其他平台这一步不发。"""
    codes = [NOVICE_REALNAME, NOVICE_REVIEW, NOVICE_LEVELS, NOVICE_LEVELS_NF, NOVICE_MODES, NOVICE_SAOLEI]
    definitions = {row.code: row for row in state.definitions_of(Medal_TextChoices.Kind.ONCE)} if state is not None else {item.code: item for item in MedalDefinition.objects.filter(active=True, kind=Medal_TextChoices.Kind.ONCE, code__in=codes)}
    for code in codes:
        definition = definitions.get(code)
        if definition is None:
            continue
        _write_once(user, definition, _once_satisfied(user, definition), state)


def evaluate_composite(user, state=None):
    """三阶档位读取自然进度，授予时查找三个难度各自最早达标的证据。"""
    definitions = [row for row in state.definitions_of(Medal_TextChoices.Kind.COMPOSITE) if row.metric == 'thrp'] if state is not None else list(MedalDefinition.objects.filter(active=True, kind=Medal_TextChoices.Kind.COMPOSITE, metric='thrp'))
    if not definitions:
        return
    codes = [code for definition in definitions for code in (definition.depends_on or [])]
    progress = state.progress if state is not None else {row.code: row for row in PlayerProgress.objects.filter(user=user, code__in=codes)}
    dependencies = state.definitions if state is not None else {row.code: row for row in MedalDefinition.objects.filter(active=True, code__in=codes)}
    memo = {}
    for definition in definitions:
        depended = list(definition.depends_on or [])
        if len(depended) < 3:
            continue
        stages = []
        for code in depended:
            row = progress.get(code)
            stages.append(0 if row is None else row.current_stage)
        stage = reached_asc_stage(definition.thresholds, min(stages) if stages else 0)
        grant = state.grants.get(definition.code) if state is not None else MedalGrant.objects.filter(user=user, definition_code=definition.code, scope_key='').first()
        if stage <= 0:
            if grant is None or grant.revoked_at is not None:
                if state is not None and definition.code in state.progress:
                    _save_progress(user, definition, 0, min(stages) if stages else 0, UNSET, UNSET, state)
                continue
            write_stage(user, definition, stage=0, current_value=min(stages) if stages else 0, state=state)
            continue
        if grant is not None and grant.revoked_at is None and grant.stage == stage:
            write_stage(user, definition, stage=stage, current_value=stage, keep_evidence=True, state=state)
            continue
        videos = _history_videos(user, definition, stage, dependencies, memo)
        if not videos:
            continue
        write_stage(
            user, definition, stage=stage, current_value=stage,
            granted_at=_completing_video(videos).upload_time, evidence={'video_ids': [video.id for video in videos]}, keep_evidence=False, state=state,
        )


def _history_dep_stage(definition, stage):
    # 复合档要求依赖已经进入这一档；不能把落在两个依赖阈值之间的原始成绩当成入档。
    return next((value for value in definition.thresholds if value >= stage), None)


def _history_candidate(user, definition, stage, video, definitions):
    if video.player_id != user.id:
        return False
    if definition.kind == Medal_TextChoices.Kind.MIN_VIDEO_ID:
        return video.id < stage
    if definition.kind == Medal_TextChoices.Kind.PB:
        return _video_qualifies(video, definition, user.id) and _meets_stage(definition, _raw_value(video, definition), stage)
    if definition.kind == Medal_TextChoices.Kind.ONCE:
        if video.state != MS_TextChoices.State.OFFICIAL:
            return False
        if definition.code == NOVICE_REVIEW:
            return True
        if definition.code == NOVICE_MODES:
            return video.mode in _mode_list(definition)
        return video.level in STANDARD_LEVELS and (definition.code != NOVICE_LEVELS_NF or video.right_ce == 0)
    for code in definition.depends_on or []:
        dependency = definitions.get(code)
        target = None if dependency is None else _history_dep_stage(dependency, stage)
        if target is not None and _history_candidate(user, dependency, target, video, definitions):
            return True
    return False


def _history_needs_refresh(user, definition, grant, definitions, video_ids, videos):
    """普通后续录像不回扫历史；证据被修改或出现更早的达标候选时才重查。"""
    watched = set(video_ids)
    evidence = grant.evidence if isinstance(grant.evidence, dict) else {}
    proof_ids = {grant.video_id, *evidence.get('video_ids', [])}
    multiple = definition.kind == Medal_TextChoices.Kind.COMPOSITE or definition.code in (NOVICE_LEVELS, NOVICE_LEVELS_NF, NOVICE_MODES)
    for entry in grant.stage_log or []:
        proof_ids.add(entry.get('evidence_id'))
        proof_ids.update(entry.get('video_ids', []))
        # 集合证据必须覆盖所有分项，才能捕捉任一分项改时。
        if multiple and not entry.get('video_ids'):
            return True
        at = parse_datetime(entry.get('at', ''))
        if at is None or timezone.is_naive(at):
            return True
        stage = entry.get('stage')
        if threshold_index(definition.thresholds, stage) < 0:
            return True
        if any(video.upload_time <= at and _history_candidate(user, definition, stage, video, definitions) for video in videos):
            return True
    return not grant.stage_log or bool(watched & proof_ids)


def _history_videos(user, definition, stage, definitions, memo):
    key = (definition.code, stage)
    if key in memo:
        return memo[key]
    if definition.kind == Medal_TextChoices.Kind.PB:
        videos = [_earliest_for_stage(user, definition, stage)]
    elif definition.kind == Medal_TextChoices.Kind.MIN_VIDEO_ID:
        videos = [VideoModel.objects.filter(player=user, id__lt=stage).order_by('upload_time', 'id').first()]
    elif definition.kind == Medal_TextChoices.Kind.COMPOSITE:
        videos = []
        for code in definition.depends_on or []:
            dependency = definitions.get(code)
            target = None if dependency is None else _history_dep_stage(dependency, stage)
            proof = None if target is None else _history_videos(user, dependency, target, definitions, memo)
            videos.append(None if not proof else proof[0])
    elif definition.code == NOVICE_REVIEW:
        videos = [_earliest_official(user)]
    elif definition.code == NOVICE_MODES:
        videos = [_earliest_official(user, mode=mode) for mode in _mode_list(definition)]
    else:
        filters = {'right_ce': 0} if definition.code == NOVICE_LEVELS_NF else {}
        videos = [_earliest_official(user, level=level, **filters) for level in STANDARD_LEVELS]
    memo[key] = videos if videos and all(video is not None for video in videos) else None
    return memo[key]


def _sync_video_history(user, definition, grant, definitions, memo):
    """重建已记录档位的达成事实；同档只留一个节点，不补造未记录过的中间档。"""
    stages = {entry.get('stage') for entry in grant.stage_log or []} | {grant.stage}
    entries = []
    current = None
    for stage in definition.thresholds:
        if stage not in stages:
            continue
        videos = _history_videos(user, definition, stage, definitions, memo)
        if not videos:
            continue
        completing = _completing_video(videos)
        entry = {'stage': stage, 'at': completing.upload_time.isoformat(), 'evidence_id': completing.id}
        if definition.kind == Medal_TextChoices.Kind.COMPOSITE or definition.code in (NOVICE_LEVELS, NOVICE_LEVELS_NF, NOVICE_MODES):
            entry['video_ids'] = [video.id for video in videos]
        entries.append((completing.upload_time, threshold_index(definition.thresholds, stage), entry))
        if stage == grant.stage:
            current = (completing, entry)
    if current is None:
        return
    entries.sort(key=lambda row: (row[0], row[1]))
    completing, entry = current
    evidence = {'video_ids': entry['video_ids']} if definition.kind == Medal_TextChoices.Kind.COMPOSITE else {'video_id': completing.id}
    if 'video_ids' in entry:
        evidence['video_ids'] = entry['video_ids']
    values = {
        'granted_at': entries[0][0], 'stage_log': [row[2] for row in entries], 'evidence': evidence,
        'video_id': None if definition.kind == Medal_TextChoices.Kind.COMPOSITE else completing.id,
    }
    fields = []
    for field, value in values.items():
        if getattr(grant, field) != value:
            setattr(grant, field, value)
            fields.append(field)
    if fields:
        grant.save(update_fields=fields)


def _refresh_video_history(user, state, video_ids=None, videos=None):
    """在发布摘要之前修正录像派生的时间、证据和日志；人工锁定始终优先。"""
    definitions = state.definitions
    memo = {}
    for code, grant in state.grants.items():
        definition = definitions.get(code)
        if definition is None or grant.revoked_at is not None or (code, '') in state.overrides:
            continue
        supported = (
            definition.kind == Medal_TextChoices.Kind.MIN_VIDEO_ID
            or (definition.kind == Medal_TextChoices.Kind.PB and definition.metric in ('timems', 'bvs', 'stnb', 'thrp') and definition.level in STANDARD_LEVELS)
            or (definition.kind == Medal_TextChoices.Kind.COMPOSITE and definition.metric == 'thrp')
            or (definition.kind == Medal_TextChoices.Kind.ONCE and code in VIDEO_ONCE_CODES)
        )
        if not supported:
            continue
        if video_ids is not None and code not in state.history_dirty and not _history_needs_refresh(user, definition, grant, definitions, video_ids, videos or []):
            continue
        _sync_video_history(user, definition, grant, definitions, memo)


def _clean_id_list(values):
    if not values:
        return []
    result = []
    seen = set()
    for value in values:
        if value is None or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _apply_shareholder_video(user, definition, video, units, new_stage, old_stage, state):
    """原始股东保留最小录像 ID 作为进度；升档证据在发布前校正为最早达标录像。"""
    old_rank = threshold_index(definition.thresholds, old_stage)
    new_rank = threshold_index(definition.thresholds, new_stage)
    if new_rank > old_rank and new_stage > 0:
        return write_stage(
            user, definition, stage=new_stage, current_value=units, best_video=video, video=video,
            granted_at=video.upload_time, evidence={'video_id': video.id}, keep_evidence=False, state=state,
        )
    return write_stage(user, definition, stage=new_stage, current_value=units, best_video=video, keep_evidence=True, state=state)


def _invalidated_levels(user, state, by_code, video_ids, found_by_id):
    """证据退审或不再达标时重算受影响的难度，不依赖另一条最佳录像。"""
    watched = set(video_ids)
    levels = set()
    for grant in state.grants.values():
        if grant.revoked_at is not None or grant.video_id not in watched:
            continue
        definition = by_code.get(grant.definition_code)
        if definition is None:
            continue
        video = found_by_id.get(grant.video_id)
        raw = None if video is None else _raw_value(video, definition)
        stands = (
            video is not None and video.player_id == user.id and _video_qualifies(video, definition, user.id)
            and _meets_stage(definition, raw, grant.stage)
        )
        if not stands:
            levels.add(definition.level)
    return levels


def _refresh_shareholder(user, state, video_ids, found):
    row = state.progress.get(SHAREHOLDER_CODE)
    override = state.overrides.get((SHAREHOLDER_CODE, ''))
    if override is not None and override.mode == 'revoke':
        return
    stored = None if row is None else row.current_value
    found_by_id = {video.id: video for video in found}
    missing = [video_id for video_id in video_ids if video_id not in found_by_id]
    left_player = [video for video in found if video.player_id != user.id and stored is not None and video.id == stored]
    if (stored is not None and stored in missing) or left_player:
        evaluate_min_video_id(user, state)
        return
    candidates = [video for video in found if video.player_id == user.id]
    if not candidates:
        return
    best = min(candidates, key=lambda video: video.id)
    if stored is not None and best.id >= stored:
        return
    definition = state.definitions.get(SHAREHOLDER_CODE)
    if definition is None:
        return
    old_stage = 0 if row is None else row.current_stage
    stage = reached_desc_stage(definition.thresholds, best.id)
    _apply_shareholder_video(user, definition, best, best.id, stage, old_stage, state)


def _highest_touched_stage(definition, videos, user_id):
    chosen = None
    stage = 0
    for video in videos:
        if not _video_qualifies(video, definition, user_id):
            continue
        candidate = _stage_of(definition, _raw_value(video, definition))
        if threshold_index(definition.thresholds, candidate) > threshold_index(definition.thresholds, stage):
            chosen, stage = video, candidate
    return chosen, stage


def _refresh_direct_pb(user, state, definitions, videos, forced_levels):
    for definition in definitions:
        if definition.level in forced_levels:
            continue
        video, new_stage = _highest_touched_stage(definition, videos, user.id)
        if video is None:
            continue
        progress = state.progress.get(definition.code)
        old_stage = 0 if progress is None else progress.current_stage
        if threshold_index(definition.thresholds, new_stage) <= threshold_index(definition.thresholds, old_stage):
            continue
        write_stage(
            user, definition, stage=new_stage, video=video, granted_at=video.upload_time,
            evidence={'video_id': video.id}, keep_evidence=False, state=state,
        )


def _video_touches_novice(code, video, user_id):
    if video.player_id != user_id or video.state != MS_TextChoices.State.OFFICIAL:
        return False
    if code == NOVICE_REVIEW:
        return True
    if code == NOVICE_LEVELS:
        return video.level in STANDARD_LEVELS
    if code == NOVICE_LEVELS_NF:
        return video.level in STANDARD_LEVELS and video.right_ce == 0
    if code == NOVICE_MODES:
        return video.mode in _mode_list_open()
    return False


def _mode_list_open():
    return set(open_modes())


def _merge_novice_set(code, extra, videos, user_id, needed_modes):
    """用这次碰到的过审录像并进已加载的数据库级别 / 模式集合。"""
    if code == NOVICE_LEVELS:
        found = set(_set_from_extra(extra, 'levels'))
        for video in videos:
            if _video_touches_novice(code, video, user_id):
                found.add(str(video.level))
        return 'levels', sorted(found), _covers(found, STANDARD_LEVELS)
    if code == NOVICE_LEVELS_NF:
        found = set(_set_from_extra(extra, 'levels'))
        for video in videos:
            if _video_touches_novice(code, video, user_id):
                found.add(str(video.level))
        return 'levels', sorted(found), _covers(found, STANDARD_LEVELS)
    if code == NOVICE_MODES:
        found = set(_set_from_extra(extra, 'modes'))
        for video in videos:
            if _video_touches_novice(code, video, user_id):
                found.add(str(video.mode))
        return 'modes', sorted(found), _covers(found, needed_modes)
    return None, [], False


def _refresh_novice(user, state, videos, invalidate_once):
    """已经授予的跳过。未授予时用状态里的级别 / 模式集合并集；凑齐才查一次证据。"""
    codes = (NOVICE_REVIEW, NOVICE_LEVELS, NOVICE_LEVELS_NF, NOVICE_MODES)
    revoked = {key for key, row in state.overrides.items() if row.mode == 'revoke'}
    definitions = {row.code: row for row in state.definitions_of(Medal_TextChoices.Kind.ONCE)}
    for code in codes:
        if (code, '') in revoked:
            continue
        definition = definitions.get(code)
        if definition is None:
            continue
        progress = state.progress.get(code)
        extra = progress.extra if progress is not None and isinstance(progress.extra, dict) else {}
        grant = state.grants.get(code)
        granted = grant is not None and grant.revoked_at is None and grant.stage > 0
        if granted and not invalidate_once:
            continue
        if invalidate_once:
            _write_once(user, definition, _once_satisfied(user, definition), state)
            continue
        if not any(_video_touches_novice(code, video, user.id) for video in videos):
            continue
        if code == NOVICE_REVIEW:
            completing = next((video for video in videos if _video_touches_novice(code, video, user.id)), None)
            if completing is None:
                continue
            write_stage(
                user, definition, stage=1, current_value=1, video=completing, best_video=completing,
                granted_at=completing.upload_time, evidence={'video_id': completing.id}, keep_evidence=False, extra=None, state=state,
            )
            continue
        set_key = 'modes' if code == NOVICE_MODES else 'levels'
        # 进度尚无集合字段时从数据库初始化，不能只合并当前录像。
        if set_key not in extra:
            _write_once(user, definition, _once_satisfied(user, definition), state)
            continue
        key, values, complete = _merge_novice_set(code, extra, videos, user.id, _mode_list(definition))
        if key is None:
            continue
        if complete:
            _write_once(user, definition, True, state)
            continue
        previous = _set_from_extra(extra, key)
        if values != previous or state.progress.get(code) is None:
            _save_progress(user, definition, 0, 0, {key: values}, None, state)


def _refresh_incremental(user, video_ids, degrade_levels, invalidate_once):
    found = list(VideoModel.objects.filter(pk__in=video_ids))
    found_by_id = {video.id: video for video in found}
    state = _EvaluationState(user)
    definitions = [row for row in state.definitions_of(Medal_TextChoices.Kind.PB) if row.metric in ('timems', 'bvs', 'stnb', 'thrp') and row.level in STANDARD_LEVELS]
    by_code = {item.code: item for item in definitions}
    forced = set(degrade_levels)
    forced.update(_invalidated_levels(user, state, by_code, video_ids, found_by_id))
    _refresh_shareholder(user, state, video_ids, found)
    _refresh_direct_pb(user, state, definitions, found, forced)
    if forced:
        evaluate_pb(user, state, levels=forced)
    _refresh_novice(user, state, found, invalidate_once)
    evaluate_composite(user, state)
    _refresh_video_history(user, state, video_ids=video_ids, videos=found)
    state.flush()
    _publish_summary(user, state)


@transaction.atomic
def refresh_player_medals(user_id, video_ids=None, degrade_levels=None, invalidate_once=False, full=False):
    """是否首次评估只读 MedalScan；增量计算复用数据库状态，与展示缓存无关。"""
    user = _lock_summary_user(user_id)
    if user is None:
        return
    ids = _clean_id_list(video_ids)
    levels = [level for level in dict.fromkeys(degrade_levels or []) if level]
    scanned = getattr(user, 'medal_scan', None) is not None
    if full or not scanned or not (ids or levels or invalidate_once):
        _evaluate_locked(user)
        return
    _refresh_incremental(user, ids, levels, bool(invalidate_once))


def revoke_manual(actor, grant_id, reason):
    grant = MedalGrant.objects.filter(pk=grant_id).first()
    if grant is None:
        raise MedalError('missing')
    return set_player_override(actor, grant.user_id, grant.definition_code, grant.scope_key, 'revoke', reason)


def _validate_override(actor, code, scope_key, mode, reason):
    if not getattr(actor, 'pk', None) or not getattr(actor, 'is_staff', False) or not getattr(actor, 'is_active', False):
        raise MedalError('actor')
    if not isinstance(code, str) or not code or len(code) > 64:
        raise MedalError('definition')
    if not isinstance(scope_key, str) or len(scope_key) > 128:
        raise MedalError('scope')
    if mode not in ('grant', 'revoke', 'auto'):
        raise MedalError('mode')
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 255:
        raise MedalError('reason')
    return reason.strip()


@transaction.atomic
def set_player_override(actor, user_id, code, scope_key, mode, reason, stage=None, granted_at=None):
    """锁定人工结果或恢复自动；自然进度始终由评估器维护，服务不负责入队。"""
    reason = _validate_override(actor, code, scope_key, mode, reason)
    user = _lock_summary_user(user_id)
    if user is None:
        raise MedalError('user')
    definition = MedalDefinition.objects.filter(pk=code).first()
    identity = {'user': user, 'definition_code': code, 'scope_key': scope_key}
    previous = MedalOverride.objects.filter(**identity).first()
    grant = MedalGrant.objects.filter(**identity).first()
    if definition is None and previous is None and grant is None:
        raise MedalError('definition')
    if mode == 'auto' and previous is None:
        return grant
    scoped_kinds = (Medal_TextChoices.Kind.MANUAL, Medal_TextChoices.Kind.EVENT_PLACE, Medal_TextChoices.Kind.GSC_STAT, Medal_TextChoices.Kind.GSC_PLACE)
    bad_scope = scope_key != scope_key.strip() or (scope_key and definition is not None and definition.kind not in scoped_kinds)
    if bad_scope and mode != 'auto' and not (mode == 'revoke' and (previous is not None or grant is not None)):
        raise MedalError('scope')
    logged_stage = None if grant is None else grant.stage
    logged_granted_at = None if grant is None else grant.granted_at
    if mode == 'grant':
        if definition is None:
            raise MedalError('definition')
        if not definition.active:
            raise MedalError('inactive')
        thresholds = definition.thresholds or ([1] if definition.kind == Medal_TextChoices.Kind.MANUAL else [])
        if type(stage) is not int or stage <= 0 or stage > 2147483647 or stage not in thresholds:
            raise MedalError('stage')
        at = granted_at or timezone.now()
        MedalOverride.objects.update_or_create(**identity, defaults={
            'mode': mode, 'stage': stage, 'granted_at': at, 'reason': reason, 'actor': actor,
        })
        evidence = {'override': True, 'reason': reason, 'actor_id': actor.pk}
        if grant is None:
            grant = MedalGrant.objects.create(
                **identity, stage=stage, granted_at=at, evidence=evidence,
                stage_log=[{'stage': stage, 'at': at.isoformat(), 'evidence_id': None}],
            )
        else:
            grant.stage_log = _append_log(grant, stage, at, None)
            grant.stage = stage
            grant.granted_at = at
            grant.video = None
            grant.participant = None
            grant.evidence = evidence
            grant.revoked_at = None
            grant.revoke_reason = ''
            grant.save(update_fields=['stage', 'stage_log', 'granted_at', 'video', 'participant', 'evidence', 'revoked_at', 'revoke_reason'])
        logged_stage = stage
        logged_granted_at = at
    else:
        if mode == 'revoke':
            MedalOverride.objects.update_or_create(**identity, defaults={
                'mode': mode, 'stage': None, 'granted_at': None, 'reason': reason, 'actor': actor,
            })
        else:
            previous.delete()
        if grant is not None and grant.revoked_at is None:
            grant.revoked_at = timezone.now()
            grant.revoke_reason = reason
            grant.save(update_fields=['revoked_at', 'revoke_reason'])
    MedalOverrideLog.objects.create(
        **identity, action=mode, stage=logged_stage, granted_at=logged_granted_at, reason=reason, actor=actor,
    )
    _publish_summary(user)
    return grant
