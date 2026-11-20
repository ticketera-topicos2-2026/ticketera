# Spec Delta

## Purpose

Defines the claims every access token of the `ticketera` realm carries: `sub`, which identifies the user, and
`realm_access.roles`, which lists the user's platform roles.

## ADDED Requirements

### Requirement: The access token identifies the user

Every access token that the `ticketera` realm issues to a user SHALL contain a `sub` claim that identifies that
user, that is the same in every token of that user, and that no other user shares.

#### Scenario: Token of a signed-in user

- **WHEN** the `CLIENT` test user signs in
- **THEN** the access token contains a non-empty `sub` claim

#### Scenario: Same user signs in twice

- **WHEN** the `CLIENT` test user signs in, signs out and signs in again
- **THEN** both access tokens have the same `sub`

#### Scenario: Same user in two sessions at the same time

- **WHEN** the `CLIENT` test user holds a session in the frontend and, at the same time, gets a token through the
  API test client
- **THEN** both access tokens have the same `sub`

#### Scenario: Different users

- **WHEN** the `CLIENT` and `EVENT_OWNER` test users sign in
- **THEN** their access tokens have different `sub` values

### Requirement: The access token carries the user's platform roles

Every access token that the `ticketera` realm issues to a user SHALL list the user's realm roles in the
`realm_access.roles` claim, including each of `ADMIN`, `EVENT_OWNER` and `CLIENT` that the user holds and none
that the user does not hold.

#### Scenario: Token of the ADMIN test user

- **WHEN** the `ADMIN` test user signs in
- **THEN** `realm_access.roles` contains `ADMIN` and contains neither `EVENT_OWNER` nor `CLIENT`

#### Scenario: Token of the EVENT_OWNER test user

- **WHEN** the `EVENT_OWNER` test user signs in
- **THEN** `realm_access.roles` contains `EVENT_OWNER` and contains neither `ADMIN` nor `CLIENT`

#### Scenario: Token of the CLIENT test user

- **WHEN** the `CLIENT` test user signs in
- **THEN** `realm_access.roles` contains `CLIENT` and contains neither `ADMIN` nor `EVENT_OWNER`
