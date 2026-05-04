"""Custom Launchpad OpenID backend with Teams extension support.

This backend extends the default LaunchpadOpenId backend to use the
Launchpad OpenID Teams extension (http://ns.launchpad.net/2007/openid-teams).
During authentication, it asks the OpenID provider which of the configured
teams the user belongs to.  The team list is stored in ``extra_data['teams']``
on the ``UserSocialAuth`` object and is consumed by the ``assign_groups``
pipeline step to keep Django groups in sync.
"""

from openid_teams.teams import TeamsRequest, TeamsResponse
from social_core.backends.launchpad import LaunchpadOpenId


class LaunchpadTeamsOpenId(LaunchpadOpenId):
    """LaunchpadOpenId backend that also queries team membership."""

    name = "launchpad"

    def get_teams(self):
        """Return the list of team names to query during authentication.

        Configurable via the ``SOCIAL_AUTH_LAUNCHPAD_TEAMS`` Django setting.
        Falls back to the teams used by the ``errors`` auth module.
        """
        # Import inside method to avoid circular imports at module load time
        from errors.auth import groups as default_teams

        return self.setting("TEAMS", default_teams)

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

    def extra_data(self, user, uid, response, details, pipeline_kwargs):
        data = super().extra_data(user, uid, response, details, pipeline_kwargs)
        data["teams"] = details.get("teams", [])
        return data
