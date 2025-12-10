import swiftclient

from errortracker import config

_client = None


def get_swift_client():
    global _client
    if _client:
        return _client

    opts = {}
    for key in ["region_name", "tenant_name"]:
        if key in config.swift_creds:
            opts[key] = config.swift_creds[key]

    _client = swiftclient.client.Connection(
        config.swift_creds["auth_url"],
        config.swift_creds["username"],
        config.swift_creds["password"],
        os_options=opts,
        auth_version=config.swift_creds["auth_version"],
    )
    _client.put_container(config.swift_bucket)
    config.logger.info("swift connected and container '%s' exists", config.swift_bucket)
    return _client
