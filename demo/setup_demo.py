"""Turn the loaded docs/screenshots/fixture.json into the local Incident Notification demo.

Run from the repository root, after `loaddata docs/screenshots/fixture.json`:

    python demo/setup_demo.py [--password <password>]

- gives the fixture's role accounts the demo email addresses and a known password,
- accepts the terms of use for them and removes any TOTP device,
- switches off the Security Objectives and Reporting modules, so only Incident
  Notification is visible (re-enable them in the admin: Functionalities > Roles).
"""

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "governanceplatform.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402
from django.utils.timezone import now  # noqa: E402
from django_otp.plugins.otp_totp.models import TOTPDevice  # noqa: E402

from governanceplatform.models import Functionality, User  # noqa: E402
from governanceplatform.permissions import set_platform_admin_permissions  # noqa: E402

DEFAULT_PASSWORD = "SerimaDemo2026!"

# fixture email -> demo email
ACCOUNTS = {
    "platform-admin@example.org": "platformadmin@bipt.be",
    "regulator-admin@example.org": "RegAdmin@bipt.be",
    "regulator-user@example.org": "RegUser@bipt.be",
    "operator-admin@example.org": "OpAdmin@bipt.be",
    "operator-user@example.org": "OpUser@bipt.be",
}


@transaction.atomic
def main(password: str) -> None:
    for fixture_email, demo_email in ACCOUNTS.items():
        user = User.objects.filter(email__iexact=demo_email).first() or User.objects.get(email=fixture_email)
        user.email = demo_email
        user.set_password(password)
        user.accepted_terms = True
        user.accepted_terms_date = now()
        user.save()
        TOTPDevice.objects.filter(user=user).delete()
        if user.groups.filter(name="PlatformAdmin").exists():
            set_platform_admin_permissions(user)
        print(f"  {demo_email:<24} {', '.join(user.groups.values_list('name', flat=True))}")

    for functionality in Functionality.objects.all():
        functionality.roles.clear()
    print("  Security Objectives and Reporting switched off (Functionality roles cleared)")


if __name__ == "__main__":
    if not settings.DEBUG:
        sys.exit("refusing to run with DEBUG off: this script sets known passwords")
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    main(parser.parse_args().password)
