from collections import Counter
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from saolei_api import AuthenticationError, RateLimitError, SaoleiError

from accountlink.models import AccountLinkQueue, AccountSaolei, Platform
from accountlink.saolei.client import saolei_client
from accountlink.saolei.services import check_binding, import_pending_saolei_videos, pending_saolei_videos, sync_saolei_metadata
from accountlink.saolei.utils import SUPPORTED_SOFTWARE
from utils.exceptions import ExceptionToResponse
from videomanager.models import VideoModel

logger = logging.getLogger('accountlink')


class Command(BaseCommand):
    help = '串行同步已绑定扫雷网账号的资料、录像目录，并补导本地未完成记录'

    def add_arguments(self, parser):
        scope = parser.add_mutually_exclusive_group(required=True)
        scope.add_argument('--all-linked', action='store_true', help='处理全部已验证且绑定一致的账号')
        scope.add_argument('--account-id', type=int, action='append', help='只处理指定扫雷网账号，可重复指定')
        parser.add_argument('--full', action='store_true', help='从 0 重新对账目录，不清空数据或回退成功游标')
        parser.add_argument('--page-size', type=int, default=200)
        parser.add_argument('--phase', choices=['all', 'metadata', 'videos'], default='all', help='先批量同步目录和详情，再下载录像；可只运行其中一个阶段')
        parser.add_argument('--limit', type=int, help='本次最多尝试导入的录像数，失败也计入；默认不限')

    def handle(self, *args, **options):
        if not 1 <= options['page_size'] <= 1000:
            raise CommandError('--page-size 必须在 1 至 1000 之间')
        if options['account_id'] and any(value <= 0 for value in options['account_id']):
            raise CommandError('--account-id 必须为正整数')
        if options['limit'] is not None and options['limit'] <= 0:
            raise CommandError('--limit 必须为正整数')
        if options['phase'] == 'videos' and options['full']:
            raise CommandError('--full 只用于 metadata 或 all 阶段')
        if options['phase'] != 'metadata' and VideoModel.objects.filter(Q(original_hash__isnull=True) | Q(original_hash='')).exists():
            raise CommandError('存量录像缺少原文件哈希；请先运行 backfill_video_hashes，避免重建时重复导入')
        counts = Counter()
        accounts = self.get_accounts(options['account_id'], counts)
        if not accounts:
            if counts['failed']:
                raise CommandError('没有可同步的账号；请检查绑定错误')
            self.stdout.write('没有符合条件的已绑定账号')
            return
        try:
            with saolei_client() as client:
                upper_bound = None
                if options['phase'] != 'videos':
                    upper_bound = client.stats().max_video_id
                    for account in accounts:
                        self.stdout.write(f'开始同步扫雷网账号#{account.pk} 目录与详情')
                        sync_saolei_metadata(account, client, upper_bound=upper_bound, counts=counts, report_failure=self.report_failure,
                                             full=options['full'], page_size=options['page_size'], progress=self.stdout.write)
                else:
                    counts['accounts'] = len(accounts)
                counts['skipped'] += sum(account.videos.filter(import_video__isnull=True).exclude(
                    software__in=SUPPORTED_SOFTWARE,
                ).count() for account in accounts)
                if options['phase'] != 'metadata':
                    pending = pending_saolei_videos(upper_bound=upper_bound, ready=True, include_rejected=True).filter(user_id__in=[account.pk for account in accounts])
                    import_pending_saolei_videos(
                        pending, client, counts=counts, report_failure=self.report_failure, limit=options['limit'], progress=self.stdout.write, ignore_rejected=True,
                    )
        except RateLimitError as exc:
            raise CommandError(f'上游限流，同步停止；Retry-After={exc.retry_after}，已提交进度保留') from exc
        except AuthenticationError as exc:
            raise CommandError('上游鉴权失败，同步停止；请检查服务器 saolei_api_key 配置') from exc
        except SaoleiError as exc:
            raise CommandError(f'上游请求失败：{type(exc).__name__}: {exc}，已提交进度保留') from exc
        except (FileNotFoundError, KeyError, ValueError) as exc:
            raise CommandError(f'配置或数据错误：{type(exc).__name__}') from exc
        self.stdout.write(f"完成：账号 {counts['accounts']}，详情 {counts['details']}，尝试 {counts['attempted']}，导入 {counts['imported']}，跳过 {counts['skipped']}，失败 {counts['failed']}")
        if counts['failed']:
            raise CommandError('部分同步或导入失败；修复后重跑命令可继续目录进度并补导未完成录像')

    def get_accounts(self, requested_ids, counts):
        links = AccountLinkQueue.objects.filter(platform=Platform.SAOLEI, verified=True).order_by('pk')
        accounts = {}
        requested = set(requested_ids) if requested_ids else None
        for link in links.iterator():
            if not link.identifier.isascii() or not link.identifier.isdecimal():
                if requested is None:
                    self.report_failure(f'关联记录#{link.pk}', ValueError(), counts)
                continue
            account_id = int(link.identifier)
            if requested is not None and account_id not in requested:
                continue
            account = AccountSaolei.objects.filter(pk=account_id, parent_id=link.userprofile_id).first()
            if account is None:
                self.report_failure(f'关联记录#{link.pk}', ExceptionToResponse('saolei', 'binding_changed', 409), counts)
                continue
            check_binding(account, link.userprofile_id)
            accounts[account.pk] = account
        for missing in (requested or set()) - accounts.keys():
            self.report_failure(f'账号#{missing}', ExceptionToResponse('saolei', 'binding_changed', 409), counts)
        return list(accounts.values())

    def report_failure(self, target, exc, counts):
        counts['failed'] += 1
        if isinstance(exc, ExceptionToResponse):
            error = f'{exc.obj}/{exc.category}'
        elif isinstance(exc, SaoleiError):
            # 客户端异常消息不含认证头或响应体，保留原因以区分响应格式与游标错误。
            error = f'{type(exc).__name__}: {exc}'
        else:
            error = type(exc).__name__
        self.stderr.write(f'{target} 失败：{error}')
        logger.error('扫雷网同步 %s 失败：%s', target, error)
