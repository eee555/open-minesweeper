from collections import Counter
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from saolei_api import AuthenticationError, RateLimitError, SaoleiError

from accountlink.models import AccountLinkQueue, AccountSaolei, Platform, SaoleiApiVideo
from accountlink.saolei.client import saolei_client
from accountlink.saolei.services import check_binding, import_saolei_video, sync_saolei_catalogue, update_saolei_account_info
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

    def handle(self, *args, **options):
        if not 1 <= options['page_size'] <= 1000:
            raise CommandError('--page-size 必须在 1 至 1000 之间')
        if options['account_id'] and any(value <= 0 for value in options['account_id']):
            raise CommandError('--account-id 必须为正整数')
        if VideoModel.objects.filter(Q(original_hash__isnull=True) | Q(original_hash='')).exists():
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
                upper_bound = client.stats().max_video_id
                for account in accounts:
                    self.stdout.write(f'开始同步扫雷网账号#{account.pk}')
                    for stage, action, kwargs in [
                        ('资料', update_saolei_account_info, {}),
                        ('目录', sync_saolei_catalogue, {'upper_bound': upper_bound, 'full': options['full'], 'page_size': options['page_size'], 'progress': self.stdout.write}),
                    ]:
                        try:
                            action(account, client, **kwargs)
                        except (AuthenticationError, RateLimitError):
                            raise
                        except Exception as exc:
                            self.report_failure(f'账号#{account.pk} {stage}', exc, counts)
                    pending = SaoleiApiVideo.objects.filter(user=account, remote_id__lte=upper_bound, import_video__isnull=True)
                    counts['skipped'] += pending.exclude(software__in=SUPPORTED_SOFTWARE).count()
                    # 同时补导以前已入库但未完成的录像，不只处理本次新增的页。
                    for source in pending.filter(software__in=SUPPORTED_SOFTWARE).select_related('user').order_by('remote_id').iterator():
                        source.user = account
                        try:
                            result = import_saolei_video(source, client)
                            counts[result] += 1
                            self.stdout.write(f'来源录像#{source.remote_id}：{result}')
                        except (AuthenticationError, RateLimitError):
                            raise
                        except Exception as exc:
                            self.report_failure(f'来源录像#{source.remote_id}', exc, counts)
                    counts['accounts'] += 1
        except RateLimitError as exc:
            raise CommandError(f'上游限流，同步停止；Retry-After={exc.retry_after}，已提交进度保留') from exc
        except AuthenticationError as exc:
            raise CommandError('上游鉴权失败，同步停止；请检查服务器 saolei_api_key 配置') from exc
        except SaoleiError as exc:
            raise CommandError(f'上游请求失败：{type(exc).__name__}，已提交进度保留') from exc
        except (FileNotFoundError, KeyError, ValueError) as exc:
            raise CommandError(f'配置或数据错误：{type(exc).__name__}') from exc
        self.stdout.write(f"完成：账号 {counts['accounts']}，导入 {counts['imported']}，跳过 {counts['skipped']}，失败 {counts['failed']}")
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
        error = f'{exc.obj}/{exc.category}' if isinstance(exc, ExceptionToResponse) else type(exc).__name__
        self.stderr.write(f'{target} 失败：{error}')
        logger.error('扫雷网同步 %s 失败：%s', target, error)
