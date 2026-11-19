# Spec Delta

## Purpose

Defines how a person signs in to and out of the frontend through the identity service, how the session is kept
alive, and how the frontend guards its pages by session and by role.

## ADDED Requirements

### Requirement: A person signs in through the identity service

The frontend SHALL sign a person in by sending them to the sign-in page of the identity service and, once they
have signed in, SHALL return them to the page they had asked for. The frontend MUST NOT ask for the password
itself.

#### Scenario: Anonymous user opens a protected page

- **WHEN** an anonymous user opens `/account`
- **THEN** the browser is sent to the sign-in page of the identity service, and after a successful sign-in the
  user is back on `/account`

#### Scenario: Sign-in cancelled or denied

- **WHEN** the identity service returns to the frontend with the error `access_denied`
- **THEN** the frontend shows that the sign-in did not complete, offers to try again, and holds no session

#### Scenario: Return to the frontend without a pending sign-in

- **WHEN** the browser reaches the frontend's sign-in return address with a result that does not match a sign-in
  the frontend started
- **THEN** the frontend shows that the sign-in did not complete and holds no session

### Requirement: Pages are guarded by session

The frontend SHALL show a page that requires a session only to a signed-in user, and SHALL start the sign-in for
anyone else.

#### Scenario: Signed-in user opens a protected page

- **WHEN** the `CLIENT` test user is signed in and opens `/account`
- **THEN** the "My account" page renders

#### Scenario: Anonymous user is not shown a protected page

- **WHEN** an anonymous user opens `/account`
- **THEN** the "My account" page does not render and the frontend calls no protected API route for it

### Requirement: Pages are guarded by role

The frontend SHALL show a page that requires a role only to a signed-in user who holds that role, and SHALL show
an access-denied page to any other signed-in user, without calling the API routes of that page.

#### Scenario: CLIENT opens an ADMIN page

- **WHEN** the `CLIENT` test user opens a page that requires the `ADMIN` role
- **THEN** the frontend shows the access-denied page and calls no API route of the `ADMIN` page

#### Scenario: EVENT_OWNER opens an ADMIN page

- **WHEN** the `EVENT_OWNER` test user opens a page that requires the `ADMIN` role
- **THEN** the frontend shows the access-denied page and calls no API route of the `ADMIN` page

#### Scenario: ADMIN opens an ADMIN page

- **WHEN** the `ADMIN` test user opens a page that requires the `ADMIN` role
- **THEN** the page renders

#### Scenario: Anonymous user opens an ADMIN page

- **WHEN** an anonymous user opens a page that requires the `ADMIN` role
- **THEN** the browser is sent to the sign-in page of the identity service instead of the access-denied page

### Requirement: The "My account" page shows the signed-in user

The frontend SHALL have a "My account" page at `/account`, guarded by session, that shows the signed-in user's
name and the platform roles they hold: those of `ADMIN`, `EVENT_OWNER` and `CLIENT` listed in the user's
`realm_access.roles`, and no other role.

#### Scenario: CLIENT opens My account

- **WHEN** the `CLIENT` test user is signed in and opens `/account`
- **THEN** the page shows that user's name and the role `CLIENT`, and no other role

#### Scenario: ADMIN opens My account

- **WHEN** the `ADMIN` test user is signed in and opens `/account`
- **THEN** the page shows that user's name and the role `ADMIN`, and no other role

#### Scenario: Default roles of the identity service are not shown

- **WHEN** a signed-in user whose `realm_access.roles` contains `CLIENT`, `offline_access`, `uma_authorization`
  and `default-roles-ticketera` opens `/account`
- **THEN** the page shows only the role `CLIENT`

### Requirement: The frontend shows who is signed in

The frontend SHALL show, on every page, the name of the signed-in user and a sign-out action, or a sign-in action
when nobody is signed in.

#### Scenario: Signed-in user

- **WHEN** the `CLIENT` test user is signed in and opens any page
- **THEN** the page shows that user's name and a sign-out action

#### Scenario: Anonymous user

- **WHEN** an anonymous user opens the status page
- **THEN** the page shows a sign-in action and no user name

### Requirement: API calls carry the access token only where it is needed

The frontend SHALL send `Authorization: Bearer <access token>` with every call of a signed-in user to a
protected API route, and SHALL call the public health routes without an `Authorization` header.

#### Scenario: Call to a protected route

- **WHEN** a signed-in user's page calls a protected API route
- **THEN** the request carries `Authorization: Bearer` followed by the user's current access token

#### Scenario: Status page of an anonymous user

- **WHEN** an anonymous user opens the status page
- **THEN** its calls to `/api/<service>/health` carry no `Authorization` header

#### Scenario: Status page of a signed-in user

- **WHEN** the `CLIENT` test user is signed in and opens the status page
- **THEN** its calls to `/api/<service>/health` carry no `Authorization` header

### Requirement: The session is renewed without interrupting the user

The frontend SHALL obtain a new access token before the current one expires, without leaving the current page,
and SHALL send the user to the sign-in page when it cannot.

#### Scenario: Access token about to expire

- **WHEN** a signed-in user stays on a page until their access token is about to expire
- **THEN** the frontend obtains a new access token, the page stays as it was, and the next API call carries the
  new token

#### Scenario: Renewal fails

- **WHEN** the frontend cannot obtain a new access token because the session at the identity service has ended
- **THEN** the frontend clears its session and sends the user to the sign-in page

### Requirement: A rejected token ends the frontend session

When an API route answers `401 Unauthorized`, the frontend SHALL clear its session and send the user to the
sign-in page, and SHALL return them afterwards to the page they were on.

#### Scenario: API answers 401

- **WHEN** a signed-in user's API call is answered `401 Unauthorized`
- **THEN** the frontend clears its session and sends the user to the sign-in page

#### Scenario: Several calls answered 401 at the same time

- **WHEN** a page makes several API calls at the same time and all are answered `401 Unauthorized`
- **THEN** the frontend sends the user to the sign-in page once

### Requirement: Signing out ends the session at the identity service

Signing out SHALL end both the frontend session and the user's session at the identity service, and MUST NOT put
the ID token or any other token in a URL.

#### Scenario: User signs out

- **WHEN** the `CLIENT` test user signs out
- **THEN** the user is back on a public page of the frontend with no session

#### Scenario: Protected page after signing out

- **WHEN** the `CLIENT` test user signs out and then opens `/account`
- **THEN** the identity service asks for the user's credentials again instead of signing them in silently

#### Scenario: No token in the sign-out address

- **WHEN** the `CLIENT` test user signs out
- **THEN** no address the browser requests during the sign-out contains the ID token or any other token

### Requirement: The status page stays public

The frontend status page SHALL keep working for an anonymous user, without starting a sign-in and whether the
identity service is available or not.

#### Scenario: Anonymous user opens the status page

- **WHEN** an anonymous user opens the status page
- **THEN** the page renders the health of every backend service without sending the user to the sign-in page

#### Scenario: Status page while the identity service is down

- **WHEN** the identity service is stopped and an anonymous user opens the status page
- **THEN** the page still renders the health of every backend service
