# GDPR compliance and data request handling

Since the Error Tracker collects sensitive user data, a lot of care must be
taken with the production environment.

It can happen that the Canonical legal team receives GDPR (or equivalents)
data request to either dump and/or remove, in which case the Error Tracker
maintainers will be contacted to provide an answer. This document helps
understanding what is being processed and how to handle the request.


## High level view of the data collection and processing


### The `whoopsie-id` identifier

The `whoopsie-id` is a long string uniquely (hopefully) identifying every Ubuntu
installation.

To find the `whoopsie-id` on a machine, simply look at the content of the
following file:
```
/var/lib/whoopsie/whoopsie-id
```

This is the only mean there is to actually identify the user data when someone
makes such request. If the data request doesn't have such an ID, you must ask
for it, or decline the processing, as there simply is no mean of making sure the
request actually comes from a legitimate user, and we want to avoid sending user
data to the wrong person.

### Where do the user data live?

When a user's machine sends a crash to `daisy.ubuntu.com`, there are two places
where the data can be stored:

1. Most of the entries in the crash report will be stored in the `OOPS` table
   of the Cassandra database, with the `key` column refering to the OOPS ID for
   each row, allowing quick retrieval of all of them. The mapping between the
   `whoopsie-id` and the newly created OOPS ID is kept in `UserOOPS`.

2. The only entry of a crash report not stored in Cassandra is the `CoreDump`
   key, which is stored temporarily in a dedicated `swift` bucket. This
   coredump, when uploaded (only when needed), is only kept for the time of the
   "retrace" to happen.
   The purpose of the "retrace" process, is to load the coredump with additional
   debugging symbols installed, so that the stacktrace newly obtained is more
   useful to developers, because it would contain source code references. If
   that "retrace" process already happened, or is not needed, the coredump is
   never uploaded and stays on a user's machine.

### Data retention policy

There is currently no fully automated data removal script in the Error Tracker.
However, there are a couple of processes in place already to avoid data staying
there forever (especially user-data).
1. When a release goes End of Life, all its OOPSes are removed. In practice,
   that means about 9 months for an interim Ubuntu release, and 5 years for an
   LTS Ubuntu release. LTS data are usually handled first by step 2 below.
2. All OOPSes are manually cleaned after a couple of years, so in practice, the
   Error Tracker only stores user data for about 3 years. Aggregated data such
   as counters or indexes might stay longer though.
3. The coredumps are always removed as soon as they've been processed, and
   they're not necessary anymore. In practice, the time to process depends on
   the length of the processing queue, and can go from a couple of minutes to
   about 10-15 days.

### Who has access?

There are two kinds of access to the data: through the web UI/API, and on the infrastructure itself.
1. From the web UI, the only Launchpad users that
   are allowed are part of the Launchpad group
   [`~error-tracker-access`](https://launchpad.net/~error-tracker-access).  
   The web UI only provides access to what's stored in Cassandra, so no coredump
   is ever accessible.
2. On the infrastructure, only some selected Canonical employee such as SREs or
   Error Tracker maintainers have access to the data. That includes coredump in
   the `swift` bucket, for the time those coredumps are waiting to be processed.


## Handling a GDPR data request

To handle such cases, the `src/tools/gdpr.py` script can be used, which takes a
`whoopsie-id` as it's primary input.

### Dumping data

The `gdpr.py` script will by default dump the data without deleting them. The
dumped data will take the form of a tarball written to the current directory,
with the following name pattern: `error-tracker-<whoopsie-id>-<date>.tar.gz`

A `--no-dump` flag is provided in case dumping is not needed.

### Deleting data

The `gdpr.py` script will by default not remove the data, to prevent accidental
data loss.

A `--remove` flag is provided in case deletion is needed.

### Answering the request

Here is an email template that can be used to answer a GDPR data request:

```
Hi [User's Name],

We have received your GDPR request for a copy of your personal data and its subsequent deletion.

1. Your data download
You can access your data dump here: [Insert Link to Data]. This link will remain active for [7 days].

2. Data deletion
As requested, we have initiated the permanent deletion of your data from our systems. This process can take up to 10 days to fully propagate across all storage nodes.

You can find more information on the data processing here: https://github.com/ubuntu/error-tracker/blob/main/GDPR.md
If you have any further questions, please reply directly to this email.

Best regards,

[Your Name/Company Name] [Contact Information]
```
