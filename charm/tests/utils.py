def check_config(juju, amqp, cassandra, swift, unit):
    # Check local config
    task = juju.exec("cat", "/home/ubuntu/error-tracker/src/local_config.py", unit=unit)
    config = task.stdout
    assert f'amqp_creds = {{\n    "host": "{amqp["host"]}"' in config, (
        "missing or wrong amqp entries in configuration"
    )
    assert f'[ "{cassandra["host"]}" ]' in config, (
        "missing or wrong cassandra entry in configuration"
    )
    assert f'"os_auth_url": {swift["os_auth_url"]}' in config, (
        "missing or wrong swift entry in configuration"
    )
