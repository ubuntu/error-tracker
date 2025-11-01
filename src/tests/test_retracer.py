# -*- coding: utf8 -*-
import time

from errortracker import cassandra_schema


class TestSubmission:
    def test_update_retrace_stats(self, retracer):
        release = "Ubuntu 12.04"
        day_key = time.strftime("%Y%m%d", time.gmtime())

        retracer.update_retrace_stats(release, day_key, 30, True)
        result = cassandra_schema.RetraceStats.get_as_dict(key=day_key.encode())
        assert result["Ubuntu 12.04:success"] == 1
        mean_key = f"{day_key}:{release}:{retracer.architecture}"
        counter_key = f"{mean_key}:count"
        result = cassandra_schema.Indexes.get_as_dict(key=b"mean_retracing_time")
        assert result[mean_key] == 30
        assert result[counter_key] == 1

        retracer.update_retrace_stats(release, day_key, 40, True)
        result = cassandra_schema.Indexes.get_as_dict(key=b"mean_retracing_time")
        assert result[mean_key] == 35
        assert result[counter_key] == 2
