from typing import Literal

from ninja import Schema
from ninja.orm import create_schema
from pydantic import Field

from ..models import QQConnectIdentity
from ..schema import SelfUserInfoOut

ProfileOut = create_schema(QQConnectIdentity, name='QQLoginProfile', fields=['nickname', 'avatar_url'])


class StartIn(Schema):
    mode: Literal['login', 'bind'] = 'login'


class StartOut(Schema):
    authorization_url: str


class StatusOut(Schema):
    user_id: int
    username: str
    configured: bool
    login_enabled: bool
    linked: bool
    profile: ProfileOut | None
    pending: ProfileOut | None
    can_unlink: bool
    has_email: bool
    can_set_username: bool


class EmailIn(Schema):
    email: str = Field(max_length=254)
    email_key: str = Field(max_length=64)
    email_captcha: str = Field(max_length=6)


class RegisteredOut(Schema):
    user: SelfUserInfoOut


class UsernameIn(Schema):
    username: str = Field(min_length=1, max_length=30)
