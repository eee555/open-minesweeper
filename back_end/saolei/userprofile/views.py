import json
import logging

from captcha.models import CaptchaStore
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from .forms import EmailForm, UserLoginForm, UserRetrieveForm
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
