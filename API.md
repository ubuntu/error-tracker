# API Endpoints

A report of every REST API endpoint found in the JavaScript source files, listing where each call is made and what parameters it uses.

---

## `/api/1.0/most-common-problems/`

- **File:** `src/errors/static/js/most_common_problems.js` (line 329)
- **Called by:** `DataSource.IO` source used by the problems data table, loaded via `interval_changed()`
- **Method:** GET
- **Parameters (query string, all optional):**
  - `format` – response format (always `json`)
  - `release` – Ubuntu release codename
  - `rootfs_build_version` – rootfs build version filter
  - `channel_name` – system-image channel name
  - `device_name` – device name
  - `device_image_version` – device image version
  - `package` – binary package name
  - `snap` – whether the package is a snap (`True`)
  - `packageset` – package set name
  - `user` – Launchpad username (subscriber filter)
  - `period` – time period (e.g. `day`, `week`, `month`)
  - `from` – start date for a custom date range
  - `to` – end date for a custom date range
  - `version` – specific package version (URL-encoded)
  - `pkg_arch` – package architecture

---

## `/api/1.0/create-bug-report/`

- **Files:**
  - `src/errors/static/js/most_common_problems.js` (line 48)
  - `src/errors/templates/bucket.html` (line 203)
- **Called by:** `createBug()` function
- **Method:** POST
- **Parameters:**
  - `format=json` (query string)
  - Request body (JSON): `{"signature": "<url-encoded signature>"}`
- **Headers:** `Content-Type: application/json`, `X-CSRFToken: <token>`

---

## `/api/1.0/package-version-is-most-recent/`

- **File:** `src/errors/static/js/most_common_problems.js` (line 78)
- **Called by:** `getPackagesState()`
- **Method:** POST (queued via `Y.io.queue`)
- **Parameters:**
  - `format=json` (query string)
  - Request body (JSON): `{"packages": [...], "release": "<release>"}` (release is optional)
- **Headers:** `Content-Type: application/json`

---

## `/api/1.0/release-package-version-pockets/`

- **File:** `src/errors/static/js/most_common_problems.js` (line 102)
- **Called by:** `getPackagesPockets()`
- **Method:** POST (queued via `Y.io.queue`)
- **Parameters:**
  - `format=json` (query string)
  - Request body (JSON): `{"packages_data": [...]}`
- **Headers:** `Content-Type: application/json`

---

## `/api/1.0/reports-state/`

- **File:** `src/errors/static/js/most_common_problems.js` (line 130)
- **Called by:** `getReportsState()`
- **Method:** POST (queued via `Y.io.queue`)
- **Parameters:**
  - `format=json` (query string)
  - Request body (JSON): `{"reports": [...], "release": "<release>"}` (release is optional)
- **Headers:** `Content-Type: application/json`

---

## `/api/1.0/binary-package-versions/`

- **File:** `src/errors/static/js/most_common_problems.js` (line 789)
- **Called by:** `package_changed()`
- **Method:** GET
- **Parameters (query string):**
  - `format=json`
  - `binary_package` – binary package name (required)
  - `release` – Ubuntu release codename (optional)

---

## `/api/1.0/system-image-versions/`

- **File:** `src/errors/static/js/most_common_problems.js` (line 812)
- **Called by:** `populate_image_versions()`
- **Method:** GET
- **Parameters (query string):**
  - `format=json`
  - `image_type` – the type of system image (required)

---

## `/api/1.0/average-crashes/`

- **File:** `src/errors/static/js/mean_time_between_failures.js` (lines 275 and 282)
- **Called by:** `mean_time_between_failures_changed()` and `mean_time_between_failures_graph()`
- **Method:** GET (data fetched via `d3.json()`)
- **Parameters (query string):**
  - `limit=0`
  - `release` – Ubuntu release codename (optional)
  - `package` – binary package name (optional)
  - `version` – specific package version (optional)

---

## `/api/1.0/average-instances/`

- **File:** `src/errors/templates/bucket.html` (line 67)
- **Called by:** inline script on the bucket detail page, passed to `mean_time_between_failures_request()`
- **Method:** GET (data fetched via `d3.json()`)
- **Parameters (query string):**
  - `limit=0`
  - `id` – bucket identifier (required)

---

## `/api/1.0/versions`

- **File:** `src/errors/templates/bucket.html` (line 127)
- **Called by:** `DataSource.IO` source for the versions table on the bucket page
- **Method:** GET
- **Parameters (query string, appended by datasource load):**
  - `limit=0`
  - `id` – bucket identifier (required)

---

## `/api/1.0/instances`

- **File:** `src/errors/templates/bucket.html` (line 216)
- **Called by:** `DataSource.IO` source for the examples/instances table on the bucket page
- **Method:** GET
- **Parameters (query string, appended by datasource load):**
  - `limit` – number of results (e.g. `100`)
  - `id` – bucket identifier (required)
  - `start` – incident ID for pagination (optional, used for infinite scroll)

---

## `/api/1.0/reports-for-system`

- **File:** `src/errors/templates/user.html` (line 23)
- **Called by:** `DataSource.Get` source for the user's crash reports table
- **Method:** GET
- **Parameters (query string, appended by datasource load):**
  - `limit` – number of results (e.g. `50`)
  - `system` – system identifier (required)

---

## `/api/1.0/retracers-average-processing-time/`

- **File:** `src/errors/static/js/retracers.js` (line 67)
- **Called by:** `retracers_graph()`
- **Method:** GET (via `Y.io`)
- **Parameters (query string):**
  - `limit=32767`
  - `format=json`

---

## `/api/1.0/retracers-results/`

- **File:** `src/errors/static/js/retracers.js` (line 95)
- **Called by:** `retracers_results_graph()`
- **Method:** GET (via `Y.io`)
- **Parameters (query string):**
  - `limit=32767`
  - `format=json`

---

## `/api/1.0/instances-count/`

- **File:** `src/errors/static/js/retracers.js` (line 122)
- **Called by:** `instances_graph()`
- **Method:** GET (via `Y.io`)
- **Parameters (query string):**
  - `limit=365`
  - `format=json`
