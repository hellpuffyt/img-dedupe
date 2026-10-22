# Security policy

## Supported versions

Only the latest commit on `main` receives fixes. There are no maintained release branches.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's advisory form:
https://github.com/hellpuffyt/img-dedupe/security/advisories/new

Do not open a public issue for a suspected vulnerability. Include the version or commit,
a minimal reproduction, and the impact you observed. You should receive an acknowledgement
within a few days; fixes are released as soon as they are verified.

## Scope

img-dedupe never modifies files during `scan`; only `apply --execute` deletes or moves files, and only those a reviewed manifest marks `delete_candidate`. Any path by which img-dedupe removes, overwrites or moves a file that was not marked, or removes the last copy of an image, is a security issue — please report it. Images are decoded with Pillow; reports about crafted images are also in scope.
