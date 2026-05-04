"""Custom social-auth pipeline steps for the errors app.

The ``assign_groups`` step keeps Django groups in sync with the Launchpad
team memberships returned by the OpenID Teams extension.
"""

from django.contrib.auth.models import Group

# List of Launchpad team names whose membership grants access to restricted views
from errors.auth import groups as known_teams


def assign_groups(backend, user, response, details, *args, **kwargs):
    """Sync Django groups with Launchpad OpenID team memberships.

    For every team name that appears both in the OpenID response *and*
    in ``errors.auth.groups``, the user is added to a Django group of
    the same name (created on the fly if needed).  Groups the user is
    no longer a member of are removed.
    """
    teams = details.get("teams", [])

    # Only consider teams we care about
    relevant = set(known_teams)
    member_of = relevant.intersection(teams)

    for team_name in member_of:
        group, _ = Group.objects.get_or_create(name=team_name)
        user.groups.add(group)

    # Remove the user from relevant groups they are no longer a member of
    no_longer = relevant - member_of
    for team_name in no_longer:
        try:
            group = Group.objects.get(name=team_name)
            user.groups.remove(group)
        except Group.DoesNotExist:
            pass
