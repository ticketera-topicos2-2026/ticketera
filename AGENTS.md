# AGENTS.md

Common rules for every AI assistant and team member in this repository (D-10). Claude Code reads this file
through `CLAUDE.md`; OpenCode and Antigravity read it directly.

The ID after each rule traces it to `docs/PLAN.md` (D-xx in section 5, RB-xx in section 2.1, PLAN n.n for a
section), to the design of `project-bootstrap` (DS-xx) or to `openspec/config.yaml`. D-35, D-36 and D-37 are team
proposals still being voted.

## Sources of truth

- Read `docs/PLAN.md`, `openspec/config.yaml` and the active change in `openspec/changes/` before working (RB-06).
- Use the ubiquitous language in `docs/domain/` once it exists (it is created after the Event Storming); never
  invent synonyms (RB-13).
- Use the role names `ADMIN`, `EVENT_OWNER` and `CLIENT` exactly (PLAN 1.1).
- Write an ADR in `docs/adr/` only for an architecture decision, and only with the
  `create-architectural-decision-record` skill (D-26, D-27).

## Method: DDD, then SDD, then TDD

- Define the contract in an OpenSpec change before writing code (RB-06, D-14).
- Name changes in English with a stage prefix: `project-bootstrap`, `e1-*`, `e2-*`, `e3-*` (D-31).
- If implementation reveals a gap in the model, stop and propose a change update; never diverge silently (PLAN 3.1).
- Write a failing test first, then the minimum code to pass, then refactor (RB-12).
- Commit the failing `test(...)` before the `feat(...)` or `fix(...)` that makes it pass (RB-12, PLAN 3.4).
- State in each test's docstring the requirement and scenario it verifies (PLAN 3.4).
- Keep test coverage of `domain` and `application` at 80 % or more (D-18).
- Work one task at a time; never implement a whole stage in one step (PLAN 6.5).

## Docker-only environment

- Never install project dependencies on the host; the host has only Git, Docker Desktop, VS Code, the assistant
  and OpenSpec (D-12).
- Run install, lint, type check, tests and migrations inside containers with `docker compose` (D-12).
- Keep the clone inside the WSL 2 file system, never under `/mnt/c` (DS-17).
- Start the whole system with a single `docker compose up` from the repository root (RB-09).
- Install dependencies only from lockfiles (`uv sync --frozen`, `npm ci`); pin every base image by digest (DS-25).
- Run pre-commit hooks inside Docker (D-19).

## Secrets

- Never commit secrets; the repository is public (RB-02).
- Put real values in `.env`, which Git ignores; keep only placeholders in `.env.example`
  (RB-02, local-environment spec).

## Architecture

- One microservice per bounded context, each in its own container (D-05).
- One logical database and credentials per service; never read another service's database (D-06).
- Expose the API only through the NGINX gateway, under `/api/<service>/`, with no version in the path (D-04, D-29).
- Use Python with FastAPI, Pydantic, SQLAlchemy 2, Alembic, uv, Ruff, mypy and pytest in the backend (D-02, D-15).
- Use PostgreSQL 18 (D-34).
- Use React, TypeScript, Vite, Vitest and React Testing Library; Tailwind CSS with shadcn/ui, installed in the
  first change with screens (D-01, D-16).
- Use hexagonal architecture (ports and adapters) in every service (D-17).

## Service internal structure

Defined by the design of `e1-idempotent-purchase` (D-33).

## Languages

- Write code, identifiers, OpenSpec artifacts and commit messages in English (D-09).
- Write `AGENTS.md` in English (D-36).
- Write `docs/PLAN.md`, `CONTRIBUTE.md` and the team log in Spanish (D-09).
- Write pull request titles in English with Conventional Commits, and pull request descriptions and review
  comments in Spanish (D-09, D-36).
- Write issue titles in English and issue bodies in Spanish (D-36).

## Branches and commits

- Never commit to `main`; every change reaches it through a pull request (RB-04).
- Work in a branch named `feature/<change-or-topic>`, one task group or one fix per branch (RB-01, PLAN 6.2).
- Use Conventional Commits for commit messages and pull request titles (PLAN 6.2, DS-21).
- Never push to or delete another member's branch, except the agreed test push of task 1.12 of
  `project-bootstrap` (D-35).
- Run `openspec update` only in a dedicated pull request (PLAN 6.5).

## Issues

- Open an issue for each OpenSpec change, each bootstrap task group, multi-file refactorings, behavior-changing
  fixes and changes to CI, Compose or shared configuration (D-20, D-37).
- For an OpenSpec change, write `Refs #n` in the planning pull request and `Closes #n` in the implementation pull
  request (D-37).
- Skip the issue for typos, wording, formatting, review fixes or minor version bumps; the pull request then says
  "Sin issue: cambio menor" and why (D-37).

## Pull requests

- Open pull requests from the template and fill every section (DS-22).
- Declare which AI assistants were used and for what, or that none was used (RB-05, PLAN 6.5).
- Reference every resolved issue with `Closes #n` (D-20).
- Get one approval from a member other than the author (RB-05, DS-21).
- Get both other members' approval for changes to `docs/PLAN.md`, `docs/domain/` or `openspec/config.yaml`
  (PLAN 6.1).
- Let AI assist a review, but only a person approves (PLAN 6.5).
- Resolve every review conversation before merging (DS-21).
- Integrate only with squash and merge; the pull request title becomes the commit on `main` (D-13, DS-21).
- Merge your own pull request once it is approved and CI is green; reviewers do not merge (D-35).
- Let GitHub delete merged branches automatically (D-35, DS-21).
- Never bypass the ruleset of `main`; revert a commit that breaks `main` (DS-21).

## Code quality and security

- Follow Clean Code: descriptive names, small single-purpose functions, no duplication, explicit error handling
  (`openspec/config.yaml`).
- Align security with OWASP ASVS and the OWASP API Security Top 10 (`openspec/config.yaml`).
