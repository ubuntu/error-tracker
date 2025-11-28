# Cassie Functions - Example Usage Scripts

This directory contains minimal example scripts demonstrating how to call each function that was migrated from `pycassa` to the `cassandra` ORM in `src/errors/cassie.py`.

## Purpose

These scripts provide:
- Clear examples of function signatures and parameters
- Sample input data for each function
- Basic usage patterns

## Important Notes

⚠️ **These are example scripts only** - They demonstrate the API but won't run successfully without:
- A properly configured Cassandra database connection
- Valid data in the database
- Required dependencies installed (cassandra-driver, numpy, etc.)

## Structure

Each file corresponds to one function in `cassie.py`:
- `get_total_buckets_by_day.py` - Example for `get_total_buckets_by_day()`
- `get_bucket_counts.py` - Example for `get_bucket_counts()`
- `get_crashes_for_bucket.py` - Example for `get_crashes_for_bucket()`
- And so on...

## Usage

To understand how to use a specific function:

1. Open the corresponding `.py` file
2. Review the function call with example parameters
3. Adapt the parameters to your use case

Example:
```bash
# View the example (won't execute without DB connection)
cat get_bucket_counts.py
```

## Functions Included

All functions migrated from pycassa to cassandra ORM:

### Bucket Operations
- `get_total_buckets_by_day` - Get bucket counts by day
- `get_bucket_counts` - Get bucket counts with filtering
- `get_crashes_for_bucket` - Get crashes for a specific bucket
- `get_package_for_bucket` - Get package info for bucket
- `get_metadata_for_bucket` - Get metadata for bucket
- `get_metadata_for_buckets` - Get metadata for multiple buckets
- `get_versions_for_bucket` - Get versions for bucket
- `get_source_package_for_bucket` - Get source package
- `get_retrace_failure_for_bucket` - Get retrace failure info
- `get_traceback_for_bucket` - Get traceback for bucket
- `get_stacktrace_for_bucket` - Get stacktrace for bucket
- `bucket_exists` - Check if bucket exists

### Crash Operations
- `get_crash` - Get crash details
- `get_crash_count` - Get crash counts over time
- `get_user_crashes` - Get crashes for a user
- `get_average_crashes` - Get average crashes per user
- `get_average_instances` - Get average instances for bucket

### Package Operations
- `get_package_crash_rate` - Analyze package crash rates
- `get_package_new_buckets` - Get new buckets for package version
- `get_binary_packages_for_user` - Get user's packages

### Retracer Operations
- `get_retracer_count` - Get retracer count for date
- `get_retracer_counts` - Get retracer counts over time
- `get_retracer_means` - Get mean retracing times

### Bug/Signature Operations
- `record_bug_for_bucket` - Record a bug for bucket
- `get_signatures_for_bug` - Get signatures for bug
- `get_problem_for_hash` - Get problem for hash

### System Image Operations
- `get_system_image_versions` - Get system image versions

## Migration Notes

These functions were migrated from the deprecated `pycassa` library to the modern `cassandra-driver` ORM while maintaining backward compatibility.
