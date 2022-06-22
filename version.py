#!/usr/bin/env python3
"""
### License
@Author: Georgiy Kulagin - kulagingol@gmail.com
@Date: 06.2022
@License: Apache License 2.0

###
Description
###
version.py - is a Python script that is required to perform simple release cycle logic for Gitlab projects.
Authentication and Authorization are based on Gitlab user-account and api-token for this account.
Gitlab target instance - should be set through GITLAB_URL env.
"""

import os
import re
import sys
from pprint import pformat

import argparse
import gitlab
import semver
from jinja2 import Template
from packaging.version import parse as pv
from loguru import logger
from requests.exceptions import ConnectionError
from gitlab.exceptions import (
    GitlabAuthenticationError,
    GitlabGetError,
    GitlabCreateError,
)

from libs.defaults import DEFAULTS
from gitlab.v4.objects import ProjectBranch, Project, ProjectTag
from gitlab.base import RESTObject


class GitlabReleaseHelper:
    """
    The main class
    """

    def __init__(self, args):
        self.args = args
        self.gl = self.__gitlab_init()
        self.target_project = self.__get_project(args.project_name)

    def __gitlab_init(self) -> gitlab.Gitlab:
        """
         Private method to define Gitlab associated Python object.

        :return: gitlab.Gitlab
        """
        try:
            gitlab_url = self.args.gitlab_url
            gitlab_api_token = self.args.gitlab_api_token
            return gitlab.Gitlab(url=gitlab_url, private_token=gitlab_api_token)
        except (GitlabAuthenticationError, ConnectionError) as e:
            logger.error(f"Check connection or Gitlab API credentials: {e}")
            sys.exit(1)

    def __get_project(self, project_name: str) -> Project:
        """
        Private method to initiate Gitlab project associated Python object.

        :param project_name: full project name group/subgroup/.../project required.
        :return: gitlab.v4.objects.Project
        """
        if project_name:
            logger.info(f"Loading {project_name} project entity.")
        else:
            logger.error("Target project is not defined, set project via argument or env variable.")
            sys.exit(1)

        try:
            return self.gl.projects.get(project_name)
        except GitlabGetError as e:
            logger.error(f"{project_name} not found: {e}")
            sys.exit(1)

    def _get_branch(self, target_branch: str) -> ProjectBranch | None:
        """
        Find branch by name.

        :param target_branch: branch name key.
        :return: gitlab.v4.objects.ProjectBranch
        """
        try:
            return self.target_project.branches.get(target_branch)
        except GitlabGetError:
            return None

    def _get_all_tags(self, refresh: bool = False) -> list[ProjectTag] | list:
        """
        Return all project tags.

        :param refresh: refresh Gitlab project object to gather the latest state.
        :return: gitlab.v4.objects.ProjectTag
        """
        if refresh:
            logger.info("Refreshing Project state.")
            self.target_project = self.__get_project(self.args.project_name)
        return self.target_project.tags.list(all=True)

    def _get_latest_rc_valid_tag(
        self, major_ver: int, refresh: bool = False
    ) -> ProjectTag | list:
        """
        Return latest project release candidate tag which is matched with pattern, see RC_RE.

        :param refresh: refresh Gitlab project object to gather the latest state.
        :param: major_ver: major release candidate version, 1 - 1.x.x, 2 - 2.x.x, etc.
        :return: gitlab.v4.objects.ProjectTag
        """
        if tags := self._get_all_tags(refresh=refresh):
            if latest_valid_rc_tags := [
                t
                for t in tags
                if re.match(pattern=DEFAULTS.get("RC_RE"), string=t.name)
                and semver.parse_version_info(t.name).major == major_ver
            ]:
                return latest_valid_rc_tags[0]
            return []
        return []

    def _get_all_rel_valid_tags(self, refresh: bool = False) -> list[ProjectTag] | list:
        """
        Return all project release tags which are matched with pattern, see REL_RE.

        :param refresh: refresh Gitlab project object to gather the latest state.
        :return: gitlab.v4.objects.ProjectTag
        """
        if tags := self._get_all_tags(refresh=refresh):
            return [
                t
                for t in tags
                if re.match(pattern=DEFAULTS.get("REL_RE"), string=t.name)
            ]
        return []

    def _get_previous_minor_rel_tag(
        self,
        target_branch: str,
        new_tag: str,
        rel_type: str,
        prefix: str = DEFAULTS.get("REL_PREFIX"),
        refresh: bool = False,
    ) -> str | None:
        """
        Return previous release tag, for example for 1.3.0 method returns 1.2.0 if 1.2.0 exists otherwise 1.1.0, etc...
        The same for new major releases 2.0.0, method returns 1.4.12 if there were no release tags before 2.0.0 besides 1.4.12.
        If there are no previous tags presented in project returns None.

        :param new_tag: new tag name to calculate previous tag.
        :param target_branch: branch name key.
        :param refresh: refresh Gitlab project object to gather the latest state.
        :param rel_type: type of release: for fix of first release.
        :param prefix: pattern for release branches, see REL_PREFIX.
        :return: str
        """
        if rel_type == "fix":
            release_base_pattern = target_branch.replace(prefix, "")
            filtered_rel_tags = [
                t.name
                for t in self._get_all_rel_valid_tags(refresh=refresh)
                if not re.match(pattern=release_base_pattern, string=t.name)
                and semver.compare(t.name, new_tag) == -1
            ]
            filtered_rel_tags.sort(key=pv, reverse=True)
            if filtered_rel_tags:
                logger.debug(f"Available sorted previous tags: {filtered_rel_tags}")
                return filtered_rel_tags[0]
            else:
                return None
        elif rel_type == "new":
            all_release_tags = [
                t.name
                for t in self._get_all_rel_valid_tags(refresh=refresh)
                if semver.compare(t.name, new_tag) == -1
            ]
            all_release_tags.sort(key=pv, reverse=True)
            if all_release_tags:
                logger.debug(f"Available sorted previous tags: {all_release_tags}")
                return all_release_tags[0]
            else:
                return None

    def _bump_new_rc_tag(self, latest_tag: ProjectTag) -> str:
        """
        Return bumped minor version for release candidate tag: 1.2.0 -> 1.3.0.

        :param latest_tag: previous release candidate tag.
        :return: str
        """
        tag_info = semver.parse_version_info(
            latest_tag.name.replace(DEFAULTS.get("RC_SUFFIX"), "")
        )
        new_bumped_tag = str(tag_info.bump_minor()) + DEFAULTS.get("RC_SUFFIX")
        logger.info(f"A new rc tag name: {new_bumped_tag}")
        return new_bumped_tag

    def _get_new_rc_tag(
        self, major_ver: int, branch: str = None, commit: str = None
    ) -> str:
        """
        Return new release candidate tag.
        !!!
        Pay attention if there are no any release candidate tag present in project method returns 1.0.0 as a first release candidate tag.
        !!!

        :param branch: optional and mostly required for log output.
        :param commit: target commit for tagging.
        :param: major_ver: major release candidate version, 1 - 1.x.x, 2 - 2.x.x, etc.
        :return: str
        """
        logger.info(
            f"Getting the latest rc tag from {self.target_project.path_with_namespace} project."
        )
        if latest_tag := self._get_latest_rc_valid_tag(major_ver=major_ver):
            logger.info(
                f"Received the latest rc tag: {latest_tag.name} which set on {latest_tag.target} commit."
            )
            return self._bump_new_rc_tag(latest_tag=latest_tag)
        else:
            logger.warning(
                f"There are no any valid tags found, new initial tag {major_ver}.0.0-rc will be set on commit {commit} in"
                f" {branch} branch."
            )
            return f'{major_ver}.0.0{DEFAULTS.get("RC_SUFFIX")}'

    def _set_new_tag(
        self, target_branch: str, target_commit: str, new_tag: str
    ) -> None:
        """
        Create a tag for a commit.

        :param target_branch: a branch which will be used to find a target commit.
        :param target_commit: target commit for tagging.
        :param new_tag: tag which will be set.
        :return: None
        """
        commits = self.target_project.commits.list(
            all=True, query_parameters={"ref_name": target_branch}
        )
        if target_commit in [c.id for c in commits]:
            try:
                self.target_project.tags.create(
                    {"tag_name": new_tag, "ref": target_commit}
                )
            except GitlabCreateError as e:
                logger.error(f"During tag creating error occurred: {e}")
        else:
            logger.error(
                f"Commit {target_commit} was not found in {target_branch} branch."
            )
            sys.exit(1)

    def create_new_rc_tag(
        self, target_branch: str, target_commit: str, major_ver: int
    ) -> None:
        """
        Create new release tag.

        :param target_branch: optional and mostly required for log output.
        :param target_commit: target commit for tagging.
        :param: major_ver: major release candidate version, 1 - 1.x.x, 2 - 2.x.x, etc.
        :return: None
        """
        new_rc_tag = semver.parse_version_info(
            self._get_new_rc_tag(
                branch=target_branch, commit=target_commit, major_ver=major_ver
            )
        )
        if target_branch := self._get_branch(target_branch=target_branch):
            self._set_new_tag(
                target_branch=target_branch.name,
                target_commit=target_commit,
                new_tag=new_rc_tag.__str__(),
            )
            logger.info(
                f"A new tag {new_rc_tag} has been set on commit {target_commit} for {target_branch.name} branch."
            )
        else:
            logger.error(f"{target_branch} branch was not found.")
            sys.exit(1)

    def create_release_branch(
        self,
        source_tag: str,
        source_branch: str,
        prefix: str = DEFAULTS.get("REL_PREFIX"),
    ) -> ProjectBranch | RESTObject:
        """
        Create new release branch from developing branch (see --project-main-branch argument).

        :param source_tag: release candidate tag to calculate new release branch name.
        :param source_branch: branch which from new release branch will be created.
        :param prefix: release branch prefix, see REL_PREFIX.
        :return: gitlab.v4.objects.ProjectBranch
        """
        release = semver.parse_version_info(
            source_tag.replace(DEFAULTS.get("RC_SUFFIX"), "")
        )
        target_branch = prefix + str(release.major) + "." + str(release.minor)
        if not (branch := self._get_branch(target_branch=target_branch)):
            logger.info(f"Creating new {target_branch} branch from {source_branch}.")
            return self.target_project.branches.create(
                {"branch": target_branch, "ref": source_branch}
            )
        else:
            logger.warning(
                f"Target branch {target_branch} is already existed in Gitlab, skipping branch creating..."
            )
            return branch

    def create_new_rel_tag(
        self, release_branch: ProjectBranch, prefix: str = DEFAULTS.get("REL_PREFIX")
    ) -> str | None:
        """
        Create new release tag based on release_branch pattern.

        :param release_branch: release branch name to set a firs release tag on.
        :param prefix: release branch prefix, see REL_PREFIX.
        :return: str
        """
        new_rel_tag = semver.parse_version_info(
            release_branch.name.replace(prefix, "") + ".0"
        )
        logger.info(f"Creating new release tag {new_rel_tag}")
        release_commit = release_branch.commit["id"]
        self._set_new_tag(
            target_branch=release_branch.name,
            target_commit=release_commit,
            new_tag=new_rel_tag.__str__(),
        )
        logger.info(
            f"A new tag {new_rel_tag.__str__()} has been set on commit {release_commit} for {release_branch.name} branch."
        )
        return new_rel_tag.__str__()

    def create_new_fix_tag(
        self, branch: str, prefix: str = DEFAULTS.get("REL_PREFIX")
    ) -> str | None:
        """
        Create new release tag with bumped fix part.

        :param branch: release branch name new tag will be calculated based on.
        :param prefix: release branch prefix, see REL_PREFIX.
        :return: str
        """
        if target_branch := self._get_branch(target_branch=branch):
            release_base_pattern = target_branch.name.replace(prefix, "")
            target_tag_group = [
                rt.name
                for rt in self._get_all_rel_valid_tags()
                if re.match(pattern=release_base_pattern, string=rt.name)
            ]
            target_tag_group.sort(key=pv, reverse=True)
            if latest_fix_tag := target_tag_group[0]:
                new_fix_tag = semver.parse_version_info(latest_fix_tag).bump_patch()
                logger.info(f"Creating new fix tag {new_fix_tag}")
                target_commit = target_branch.commit["id"]
                self._set_new_tag(
                    target_branch=target_branch.name,
                    target_commit=target_branch.commit["id"],
                    new_tag=new_fix_tag.__str__(),
                )
                logger.info(
                    f"A new tag {new_fix_tag.__str__()} has been set on commit {target_commit} for {target_branch.name} branch."
                )
                return new_fix_tag.__str__()

    def _get_release_commits(self, source: str, target: str) -> list:
        """
        Return all release commit for release branch only, exclude ancestor commits.

        :param source: source tag/branch name compare from.
        :param target: target tag/branch name compare to.
        :return: list
        """
        logger.info(f"Generating diff between {source} and {target}.")
        return self.target_project.repository_compare(from_=source, to=target).get(
            "commits", []
        )

    def _get_commit_diff(self, commit: str) -> dict:
        """
        Return refactored commit diff.

        :param commit: commit sha.
        :return: dict
        """
        target_commit = self.target_project.commits.get(commit)
        commit_diff = [{"change_for": d.get("new_path")} for d in target_commit.diff()]
        return {
            "commit_id": target_commit.id,
            "commit_url": target_commit.web_url,
            "commit_author": target_commit.author_name,
            "title": target_commit.title,
            "committed_date": target_commit.committed_date,
            "stats": target_commit.stats,
            "diff": commit_diff,
        }

    def _prepare_release_changelog(self, source: str, target: str) -> list:
        """
        Return commit for changelog only.

        :param source: source tag/branch name compare from.
        :param target: target tag/branch name compare to.
        :return: list
        """
        release_commits = self._get_release_commits(source=source, target=target)
        return [self._get_commit_diff(rc.get("id")) for rc in release_commits]

    def _template_release_scheme(self, changelog: list) -> str:
        """
        Return templated Jinja2 string based on provided changelog.

        :param changelog: a dict with changes.
        :return: str
        """

        with open(self.args.release_template, 'r') as file_:
            template = Template(file_.read())
        return template.render(changelog_data=changelog)

    def create_release_entity(
        self, source_branch: str, release_branch: str, new_tag: str, rel_type: str
    ) -> None:
        """
        Create Gitlab Release.

        :param source_branch: source release branch for generating change log if no previous release tags available.
        :param release_branch: release branch name to calculate previous release tag.
        :param new_tag: tag for calculating Release name.
        :param rel_type: type of release: for fix of first release.
        :return: None
        """
        logger.info(f"Preparing Release for {release_branch} release branch.")
        previous_minor_rel_tag = self._get_previous_minor_rel_tag(
            target_branch=release_branch, new_tag=new_tag, rel_type=rel_type
        )
        if previous_minor_rel_tag:
            changelog = self._prepare_release_changelog(
                source=previous_minor_rel_tag, target=new_tag
            )
        else:
            changelog = self._prepare_release_changelog(
                source=source_branch, target=new_tag
            )
        release_scheme = self._template_release_scheme(changelog=changelog)
        payload = {
            "name": f"Release {new_tag}",
            "tag_name": f"{new_tag}",
            "description": f"{release_scheme}",
        }
        self.target_project.releases.create(payload)


def main():
    """
    The main()
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-name",
        default=os.getenv("GITLAB_TARGET_PROJECT", ""),
        help="The target project for release cycle.",
    )
    parser.add_argument(
        "--gitlab-api-token",
        default=os.getenv("GITLAB_API_TOKEN", ""),
        help="Gitlab API token for authorization",
    )
    parser.add_argument(
        "--gitlab-url",
        default=os.getenv("GITLAB_URL", "https://gitlab.com"),
        help="Gitlab API instance URL",
    )
    parser.add_argument(
        "--verbose",
        default="INFO",
        action="store_const",
        const="DEBUG",
        help="Debug verbose output",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["create-rc-tag", "promote-release", "create-fix-tag"],
        help="Modes: \
            [create-rc-tag] - create initial or bump rc tag based on the latest release candidate tag. \
            [promote-release] - cut release/ branch and create release tag. \
            [create-fix-tag] - bump fix part for release tag.",
    )
    parser.add_argument(
        "--tag",
        help="A tag which will be promoted to release tag",
    )
    parser.add_argument(
        "--branch",
        help="A branch which will be used for a new tag",
    )
    parser.add_argument(
        "--commit",
        help="A commit hash which will be used for a new tag",
    )
    parser.add_argument(
        "--release-template",
        default=os.getenv("GITLAB_RELEASE_TEMPLATE", "./release_templates/default.j2"),
        help="A path to release notes Jinja2 template.",
    )
    parser.add_argument(
        "--project-main-branch",
        default=os.getenv("GITLAB_MAIN_BRANCH", "master"),
        help="A main branch which we use to cut a release/ or generate Release notes if no tags.",
    )
    parser.add_argument(
        "--major-ver",
        default=os.getenv("GITLAB_MAJOR_RELEASE", 1),
        help="A major part of X.x.x release pattern.",
    )

    args = parser.parse_args()
    logger.remove()
    logger.configure(handlers=[DEFAULTS.get("LOGURU_CONFIG")[args.verbose]])
    logger.debug(f"Provided arguments: \n {pformat(args.__dict__)}")
    logger.debug(f"Loaded defaults: \n {pformat(DEFAULTS)}")

    if not args.gitlab_api_token:
        logger.error("Gitlab API token is missed.")
        sys.exit(1)

    if args.mode in ["create-rc-tag", "create-fix-tag"] and not (
        args.commit and args.branch
    ):
        logger.error(
            f"--mode {args.mode} requires --commit <sha> --branch <branch-name> arguments."
        )
        sys.exit(1)
    elif args.mode == "promote-release" and not args.tag:
        logger.error(f"--mode {args.mode} requires --tag <tag> key-value argument.")
        sys.exit(1)

    grh = GitlabReleaseHelper(args)

    if args.mode == "create-rc-tag":
        grh.create_new_rc_tag(
            target_branch=args.branch,
            target_commit=args.commit,
            major_ver=args.major_ver,
        )
    elif args.mode == "promote-release":
        release_branch = grh.create_release_branch(
            source_tag=args.tag, source_branch=args.project_main_branch
        )
        new_rel_tag = grh.create_new_rel_tag(release_branch=release_branch)
        if new_rel_tag:
            grh.create_release_entity(
                source_branch=args.project_main_branch,
                release_branch=release_branch.name,
                new_tag=new_rel_tag,
                rel_type="new",
            )
    elif args.mode == "create-fix-tag":
        new_fix_tag = grh.create_new_fix_tag(branch=args.branch)
        if new_fix_tag:
            grh.create_release_entity(
                source_branch=args.project_main_branch,
                release_branch=args.branch,
                new_tag=new_fix_tag,
                rel_type="fix",
            )


if __name__ == "__main__":
    main()
