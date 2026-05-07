from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from openid_teams.teams import TeamsRequest, TeamsResponse
from social_core.backends.launchpad import LaunchpadOpenId

allowed_teams = [
    "error-tracker-access",
]


def can_see_stacktraces(func):
    def in_groups(u):
        return u.groups.filter(name__in=allowed_teams).count() > 0

    return login_required(user_passes_test(in_groups, login_url="/login-failed")(func))


class LaunchpadTeamsOpenId(LaunchpadOpenId):
    """Custom Launchpad OpenID backend with Teams extension support.

    This backend extends the default LaunchpadOpenId backend to use the
    Launchpad OpenID Teams extension (http://ns.launchpad.net/2007/openid-teams).
    During authentication, it asks the OpenID provider which of the configured
    teams the user belongs to.  The team list is stored in ``extra_data['teams']``
    on the ``UserSocialAuth`` object and is consumed by the ``assign_groups``
    pipeline step to keep Django groups in sync.
    """

    name = "launchpad"

    def get_teams(self):
        """Return the list of team names to query during authentication.

        Configurable via the ``SOCIAL_AUTH_LAUNCHPAD_TEAMS`` Django setting.
        Falls back to the teams used by the ``errors`` auth module.
        """
        return self.setting("TEAMS", allowed_teams)

    def setup_request(self, params=None):
        """Extend the OpenID request with a Teams extension."""
        openid_request = super().setup_request(params)

        teams_request = TeamsRequest(requested=self.get_teams())
        openid_request.addExtension(teams_request)

        return openid_request

    def get_user_details(self, response):
        """Add 'teams' to the details dict returned by the backend."""
        details = super().get_user_details(response)

        teams_response = TeamsResponse.fromSuccessResponse(response)
        details["teams"] = teams_response.teams if teams_response else []

        return details

    def extra_data(self, user, uid, response, details, **pipeline_kwargs):
        data = super().extra_data(user, uid, response, details, **pipeline_kwargs)
        data["teams"] = details.get("teams", [])
        return data


def assign_groups(backend, user, response, details, *args, **kwargs):
    """Sync Django groups with Launchpad OpenID team memberships.

    For every team name that appears both in the OpenID response *and*
    in ``errors.auth.groups``, the user is added to a Django group of
    the same name (created on the fly if needed).  Groups the user is
    no longer a member of are removed.
    """
    teams = details.get("teams", [])

    # Only consider teams we care about
    relevant = set(allowed_teams)
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
