### License
- Author: Georgiy Kulagin - kulagingol@gmail.com
- Date: 06.2022
- License: Apache License 2.0

### Description

version.py - is a Python script that is required to perform simple release cycle logic for Gitlab projects.
Authentication and Authorization are based on Gitlab user-account and api-token for this account.
Gitlab target instance - should be set through GITLAB_URL env.

### Supported release cycle
Supported release cycle description you can find in [docs](docs/release_cycle.md).

### Available modes

* **create-rc-tag** - create initial or incremented tag based on the latest release candidate tag;
* **promote-release** - cut release/ branch and create release tag, create Gitlab Release;
* **create-fix-tag** - bump fix part for release tag, create Gitlab Release;

### Script arguments

* **--project-name** (Required)(Default: GITLAB_TARGET_PROJECT) - target project for release cycle.
* **--gitlab-url** (Required)(Default: GITLAB_URL, https://gitlab.com/) - Gitlab API instance URL.
* **--gitlab-api-token** (Required)(Default: comes from GITLAB_API_TOKEN env) - Gitlab API authorization token.
* **--verbose** (Optional)(Default: INFO) - set a verbose output for logger.
* **--mode** (Required) -[create-rc-tag, promote-release, create-fix-tag] - see Available modes article.
* **--tag** (Depends on mode) - tag which will be promoted.
* **--branch** (Depends on mode - a branch name to set a tag for, mostly it requires for log output.
* **--commit** (Depends on mode - a commit sha to set a tag for.
* **--release-template** (Optional)(Default: GITLAB_RELEASE_TEMPLATE, ./release_templates/default.j2) - A path to release notes Jinja2 template.
* **--project-main-branch** (Optional) - a main branch which we use to cut a release/ or generate Release notes if no tags.
* **--major-ver** (Optional)(Default: 1) - A major part of X.x.x release pattern.
* **--output-file** (Optional)(Default: OUTPUT_FILE_NAME, ./output.yaml) - A log file with project name and generated tag.

### How to use

#### Via env variables declaration:
```bash
export GITLAB_URL=https://gitlab.com/
export GITLAB_API_TOKEN=my_awesome_gitlab_token
export GITLAB_TARGET_PROJECT=my-awesome-group/my-awesome-project

python3 version.py --mode create-rc-tag \
                   --commit sha \
                   --branch my-awesome-branch
```
#### Via script arguments:
```bash
python3 version.py --project-name my-awesome-project \
                   --gitlab-url my-awesome-gtilab \
                   --gitlab-api-token my-awesome-token \
                   --mode create-rc-tag \
                   --commit sha \
                   --branch my-awesome-branch
```

### Release templates:
Release templates it's a Jinja2 templates from ./release_templates folder.
Might be customizable, but feature is not released yet.

### Requirements

Main interpreter python 3.10.4

#### libs:
- loguru==0.6.0
- python-gitlab==3.5.0
- requests==2.27.1
- semver==2.13.0
- packaging==21.3
- Jinja2==3.1.1
- PyYAML==6.0

### TODO:
1. Compose a lib for importing and rendering different release notes Jinja2 templates.
2. Move Gitlab API related logic to the individual module. It's required for implementing a compatibility with GitHub API and make the script more flexible.
3. ...