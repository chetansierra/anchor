# Security and Compliance

Security is foundational to Nimbus. This page summarizes our practices and
certifications.

**Certifications.** Nimbus is **SOC 2 Type II** certified and undergoes an annual
audit. A copy of the report is available under NDA from your account manager. We
are also working toward ISO 27001.

**Encryption.** All data is encrypted in transit with TLS 1.2+ and at rest with
AES-256. Database backups are encrypted as well.

**Access controls.** Support role-based access, custom roles, SAML SSO, SCIM
provisioning, and enforced two-factor authentication (see the related help
articles). Internally, employee access to customer data is least-privilege,
logged, and reviewed.

**Audit logs (Enterprise).** A tamper-evident log of sign-ins, permission changes,
and data exports, retained for 1 year and exportable via API.

**Infrastructure.** Hosted on major cloud providers with DDoS protection, a web
application firewall, and 24/7 monitoring. We run regular third-party penetration
tests and operate a responsible-disclosure program at security@nimbus.example.

**Reliability.** See *Uptime and SLA* for availability commitments. For privacy and
data-handling details, see *Data Retention and GDPR*.
