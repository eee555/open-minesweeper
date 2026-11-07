from ninja.orm import create_schema
from pydantic import Field

from ..models import AccountGitHub

GitHubAccountOut = create_schema(AccountGitHub, custom_fields=[('id', str, Field(coerce_numbers_to_str=True))])
