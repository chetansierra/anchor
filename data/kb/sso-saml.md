# Single Sign-On (SAML/SSO)

Nimbus supports **SAML 2.0 single sign-on** on the Enterprise plan. SSO lets your
team sign in through your identity provider (IdP) — Okta, Azure AD / Entra ID,
Google Workspace, OneLogin, or any SAML 2.0 provider.

**Setting up SAML SSO:**

1. Go to **Settings → Security → Single Sign-On** (Enterprise only).
2. Copy the Nimbus **ACS URL** and **Entity ID** into a new SAML app in your IdP.
3. Paste your IdP's **metadata URL** (or upload the metadata XML) back into Nimbus.
4. Map the `email` and `name` SAML attributes.
5. Send yourself a test assertion, then click **Enable SSO**.

**SCIM provisioning** is also available so users are created and deactivated in
Nimbus automatically when they're added or removed in your IdP.

Once SSO is enforced, members sign in via your IdP and **password-based login and
self-service password reset are disabled** — account access is governed entirely
by your identity provider. You can allow a break-glass admin to keep password
access in case of IdP outage. SAML SSO is not available on Starter or Growth; talk
to sales to move to Enterprise.
