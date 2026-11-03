# Spec Delta

## Purpose

Defines how changes reach `main`: only through reviewed pull requests from feature branches, with the required
reviewers, passing required checks, resolved conversations, test-first commits, declared AI usage and squash
merges, so every change is verified by another team member before integration.

## ADDED Requirements

### Requirement: Changes reach main only through pull requests

The repository SHALL reject any direct push, force push or deletion of the `main` branch. The rule applies to
every team member, including repository administrators and organization owners, with no bypass.

#### Scenario: Direct push to main is rejected

- **WHEN** a team member pushes a commit directly to `main`
- **THEN** the push is rejected and `main` is unchanged

#### Scenario: Force push to main is rejected

- **WHEN** a team member force-pushes to `main`
- **THEN** the push is rejected and the history of `main` is unchanged

#### Scenario: Deletion of main is rejected

- **WHEN** a team member tries to delete the `main` branch
- **THEN** the deletion is rejected

#### Scenario: An administrator pushes directly to main

- **WHEN** a repository administrator or organization owner pushes a commit directly to `main`
- **THEN** the push is rejected and `main` is unchanged

### Requirement: Each task is developed in its own feature branch

Every pull request to `main` SHALL come from a branch named `feature/<change-or-topic>` that contains the work of
one task group or one fix.

#### Scenario: Pull request from a feature branch

- **WHEN** a team member opens a pull request from `feature/bootstrap-catalog` to `main`
- **THEN** the pull request is eligible for review

#### Scenario: Pull request from a branch outside the convention

- **WHEN** a pull request to `main` comes from a branch whose name does not start with `feature/`
- **THEN** the reviewer requests changes and the pull request is not merged

### Requirement: Merging requires approval from a member other than the author

A pull request to `main` MUST have at least one approval from a team member other than its author.

#### Scenario: Pull request without approval

- **WHEN** a pull request to `main` has no approving review
- **THEN** the merge is blocked

#### Scenario: Author approves their own pull request

- **WHEN** the author of a pull request tries to approve it
- **THEN** the approval does not count toward the requirement and the merge stays blocked

#### Scenario: Pull request approved by another member

- **WHEN** a team member other than the author approves the pull request
- **THEN** the approval requirement is met

### Requirement: The most recent push is approved by someone other than its pusher

The most recent push to a pull request to `main` MUST be approved by a team member other than the person who
made that push.

#### Scenario: Reviewer pushes a commit and then approves

- **WHEN** the reviewer of a pull request pushes a commit to its branch and then approves the pull request
- **THEN** the merge stays blocked until another team member approves

#### Scenario: Author pushes and another member approves

- **WHEN** the author makes the most recent push and another team member approves after it
- **THEN** the requirement is met

### Requirement: Approvals are dismissed when new commits are pushed

An approval of a pull request to `main` SHALL be dismissed when a new commit is pushed to its branch.

#### Scenario: New commit after approval

- **WHEN** a pull request is approved and its author then pushes a new commit
- **THEN** the approval is dismissed and the merge is blocked until a new approval is given

### Requirement: Shared planning files require approval from both other members

A pull request to `main` that changes `docs/PLAN.md`, any file under `docs/domain/` or `openspec/config.yaml`
MUST be approved by both team members other than its author.

#### Scenario: Only one of the other members approved

- **WHEN** a pull request authored by member A changes `docs/PLAN.md` and only member B has approved it
- **THEN** the pull request is not merged until member C also approves

#### Scenario: Both other members approved

- **WHEN** a pull request authored by member A changes `openspec/config.yaml` and members B and C have approved it
- **THEN** the approval requirement is met

### Requirement: Reviewers are requested automatically by path

Opening a pull request to `main` SHALL request a review automatically from the team member assigned, in the
cross-review assignment of `docs/PLAN.md` section 6.1, to the paths the pull request changes.

#### Scenario: Pull request that changes the catalog service

- **WHEN** a team member opens a pull request that changes files under `services/catalog/`
- **THEN** a review is requested from the member assigned to review `catalog`

#### Scenario: Pull request that changes shared planning files

- **WHEN** a team member opens a pull request that changes `docs/PLAN.md`
- **THEN** a review is requested from both other team members

### Requirement: Unresolved review conversations block the merge

A pull request to `main` MUST NOT be merged while any review conversation on it is unresolved.

#### Scenario: Unresolved conversation

- **WHEN** an approved pull request with every required check passing has one unresolved review conversation
- **THEN** the merge is blocked

#### Scenario: All conversations resolved

- **WHEN** every review conversation on the pull request is resolved
- **THEN** the conversation requirement is met

### Requirement: Failing required checks block the merge

A pull request to `main` MUST NOT be merged while any required status check (`openspec-validate`, `quality`,
`smoke-test`) is failing, pending or missing.

#### Scenario: A required check fails

- **WHEN** an approved pull request has the `quality` check failing
- **THEN** the merge is blocked

#### Scenario: A required check is still running

- **WHEN** an approved pull request has the `smoke-test` check pending
- **THEN** the merge is blocked until the check passes

### Requirement: Pull requests are integrated only by squash and merge

A pull request to `main` SHALL be integrated only as a single squash commit, and its feature branch SHALL be
deleted from the remote repository after the merge.

#### Scenario: Squash and merge

- **WHEN** a team member merges an eligible pull request with squash and merge
- **THEN** `main` receives exactly one new commit and the feature branch is deleted from the remote repository

#### Scenario: Merge commit or rebase merge attempted

- **WHEN** a team member tries to integrate a pull request with a merge commit or a rebase merge
- **THEN** that merge method is not available and `main` is unchanged

### Requirement: Behavior changes are committed test first

A pull request that changes behavior SHALL contain a `test(...)` commit adding a failing test before the
`feat(...)` or `fix(...)` commit that makes it pass.

#### Scenario: Test commit before the feature commit

- **WHEN** a pull request contains `test(catalog): ...` followed by `feat(catalog): ...` that makes the test pass
- **THEN** the pull request meets the requirement

#### Scenario: Feature commit with no previous test commit

- **WHEN** a pull request that changes behavior contains a `feat(...)` commit with no previous `test(...)` commit
- **THEN** the reviewer requests changes

### Requirement: Pull request titles follow Conventional Commits

The title of every pull request to `main` SHALL follow Conventional Commits, because it becomes the message of the
squash commit on `main`.

#### Scenario: Title outside the convention

- **WHEN** a pull request to `main` is titled "Catalog changes"
- **THEN** the reviewer requests changes

#### Scenario: Title within the convention

- **WHEN** a pull request to `main` is titled "feat(catalog): add health endpoint"
- **THEN** the squash commit on `main` carries that title as its message

### Requirement: Pull requests reference the issues they resolve

A pull request that resolves a GitHub issue SHALL reference it in its description with `Closes #n`.

#### Scenario: Pull request that resolves an issue

- **WHEN** a pull request whose description contains `Closes #12` is merged
- **THEN** issue #12 is closed

#### Scenario: Missing issue reference

- **WHEN** a pull request resolves an issue but its description does not reference it with `Closes #n`
- **THEN** the reviewer requests changes

### Requirement: Every pull request declares AI usage

Every pull request to `main` SHALL declare which AI assistants were used and for what, or state that none was
used; a pull request without that declaration MUST NOT be approved.

#### Scenario: Pull request opened from the template

- **WHEN** a team member opens a pull request to `main`
- **THEN** the description contains an AI usage section to complete

#### Scenario: AI usage section left empty

- **WHEN** a pull request reaches review with the AI usage section empty
- **THEN** the reviewer requests changes and does not approve it
