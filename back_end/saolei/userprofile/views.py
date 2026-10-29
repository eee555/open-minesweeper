import json
import logging
import os

from captcha.models import CaptchaStore
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from msuser.models import UserMS
from .decorators import staff_required
from .forms import EmailForm, UserLoginForm, UserRegisterForm, UserRetrieveForm
from .models import EmailVerifyRecord, UserProfile
from .services import judge_email_verification, send_email, user_metadata
from .utils import judge_captcha

logger = logging.getLogger('userprofile')


@ratelimit(key='ip', rate='60/h')
@require_POST
# 用账号、密码登录
# 此处要分成两个，密码容易碰撞，hash难碰撞
def user_login(request):
    data = request.POST
    if not UserLoginForm(data=data).is_valid():
        return HttpResponseBadRequest()
    capt = data['captcha']   # 用户提交的验证码
    key = data['hashkey']    # 验证码hash
    username = data['username']
    if not judge_captcha(capt, key):
        logger.info(f'用户 {username} 验证码错误')
        return JsonResponse({'type': 'error', 'object': 'login', 'category': 'captcha'})
    # 检验账号、密码是否正确匹配数据库中的某个用户
    # 如果均匹配则返回这个 user 对象
    if not (user := authenticate(username=username, password=data['password'])):
        logger.info(f'用户 {username} 账密错误')
        return JsonResponse({'type': 'error', 'object': 'login', 'category': 'password'})
    # 将用户数据保存在 session 中，即实现了登录动作
    login(request, user)
    request.session.set_expiry(int(data['set_expiry']) * 86400)
    if 'user_id' in data and data['user_id'] != str(user.id):
        # 检测到小号
        logger.warning(f'{data["user_id"][:50]} is different from {str(user.id)}.')
    return JsonResponse({'type': 'success', 'user': user_metadata(user, user)})


def user_logout(request):
    logout(request)
    return HttpResponse()


# 用户找回密码
@ratelimit(key='ip', rate='60/h')
@require_POST
def user_retrieve(request):
    user_retrieve_form = UserRetrieveForm(data=request.POST)
    if not user_retrieve_form.is_valid():
        return HttpResponseBadRequest()
    emailHashkey = request.POST.get('email_key')
    email_captcha = request.POST.get('email_captcha')
    email = request.POST.get('email')
    if not judge_email_verification(email, email_captcha, emailHashkey):
        return JsonResponse({'type': 'error', 'object': 'emailcode'})
    if not (user := UserProfile.objects.filter(email=user_retrieve_form.cleaned_data['email']).first()):
        return HttpResponseNotFound()  # 前端已经查过重了，理论上不应该进到这里
    # 设置密码(哈希)
    user.set_password(user_retrieve_form.cleaned_data['password'])
    user.save(update_fields=['password', 'date_updated'])
    # 保存好数据后立即登录
    login(request, user)
    logger.info(f'用户 {user.username}#{user.id} 邮箱找回密码')
    EmailVerifyRecord.objects.filter(hashkey=emailHashkey).delete()
    return JsonResponse({'type': 'success', 'user': user_metadata(user, user)})


# 用户注册
# @method_decorator(ensure_csrf_cookie)
@ratelimit(key='ip', rate='6/h')
@require_POST
def user_register(request):
    user_register_form = UserRegisterForm(data=request.POST)
    if user_register_form.is_valid():
        emailHashkey = request.POST.get('email_key')
        email_captcha = request.POST.get('email_captcha')
        email = request.POST.get('email')
        if judge_email_verification(email, email_captcha, emailHashkey):
            new_user = user_register_form.save(commit=False)
            # 设置密码(哈希)
            new_user.set_password(
                user_register_form.cleaned_data['password'])
            new_user.is_active = True  # 自动激活
            user_ms = UserMS.objects.create()
            new_user.userms = user_ms
            user_ms.save()  # noqa: DJM100
            new_user.save()  # noqa: DJM100
            # 保存好数据后立即登录
            login(request, new_user)
            logger.info(f'用户 {new_user.username}#{new_user.id} 注册')
            # 顺手把过期的验证码删了
            EmailVerifyRecord.objects.filter(hashkey=emailHashkey).delete()
            return JsonResponse({'type': 'success', 'user': user_metadata(new_user, new_user)})
        else:
            return JsonResponse({'type': 'error', 'object': 'emailcode'})
    else:
        if 'email' not in user_register_form.cleaned_data or 'username' not in user_register_form.cleaned_data:
            # 可能发生前端验证正确，而后端验证不正确（后端更严格），此时clean会直接删除email字段
            # 重复的邮箱、用户名也会被删掉
            errors_dict = json.loads(user_register_form.errors.as_json())
            errors = list(errors_dict.values())[0]
            return JsonResponse({'status': 105, 'msg': errors[0]['message']})
        else:
            return JsonResponse({'status': 101, 'msg': user_register_form.errors.as_text().split('*')[-1]})


@require_GET
def check_collision(request):
    user = None
    if username := request.GET.get('username'):
        user = UserProfile.objects.filter(username=username).first()
    elif email := request.GET.get('email'):
        user = UserProfile.objects.filter(email=email).first()
    else:
        return HttpResponseBadRequest()
    if not user:
        return HttpResponse(False)
    return HttpResponse(True)


# 【管理员】删除用户的个人信息，从服务器磁盘上完全删除，但不影响是否封禁
# 站长可以删除管理员信息（如果站长也是管理员）。
# http://127.0.0.1:8000/userprofile/del_user_info/?id=1
@require_GET
@staff_required
def del_user_info(request):
    user = UserProfile.objects.get(id=request.GET['id'])
    if user.is_staff and not request.user.is_superuser:
        return HttpResponse('没有删除管理员信息的权限！')
    logger.info(f'管理员 {request.user.username}#{request.user.id} 删除用户 {user.username}#{user.id}')
    user.realname = ''
    user.signature = ''
    if user.avatar and os.path.isfile(user.avatar.path):
        os.remove(user.avatar.path)
    user.avatar = None


# 创建验证码
@ratelimit(key='ip', rate='60/h')
def captcha(request):
    if settings.E2E_TEST:
        # Create a fixed captcha for E2E tests
        captcha_obj = CaptchaStore.objects.create(challenge='test', response='test')
        hashkey = captcha_obj.hashkey
    else:
        hashkey = CaptchaStore.generate_key()

    return {'hashkey': hashkey}


# 刷新验证码
@ratelimit(key='ip', rate='60/h')
def refresh_captcha(request):
    c = captcha(request)
    c.update({'status': 100})
    return HttpResponse(json.dumps(c), content_type='application/json')


# 验证验证码，若通过，发送email
@ratelimit(key='ip', rate='1/m')
@require_POST
def get_email_captcha(request):
    data = request.POST
    email_form = EmailForm(data=data)
    if not email_form.is_valid():  # 正常工作的前端不应当发出的请求
        return HttpResponseBadRequest()
    capt = data.get('captcha')
    key = data.get('hashkey')
    if not judge_captcha(capt, key):  # 图形验证码不对
        return JsonResponse({'type': 'error', 'object': 'captcha'})
    if settings.EMAIL_SKIP and not settings.E2E_TEST:
        code, hashkey = send_email(data.get('email'), data.get('type'))
        return JsonResponse({'type': 'success', 'code': code, 'hashkey': hashkey})
    if hashkey := send_email(data.get('email'), data.get('type')):  # 邮件发送成功
        return JsonResponse({'type': 'success', 'hashkey': hashkey})
    else:  # 邮件发送失败
        return JsonResponse({'type': 'error', 'object': 'email'})
