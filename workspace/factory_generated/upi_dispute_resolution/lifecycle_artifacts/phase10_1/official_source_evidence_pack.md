# Phase 10.1 Official Source Evidence Pack — upi_dispute_resolution

## Purpose

This evidence pack records official-source references that may guide
requirements, architecture, economics, and regulatory-alignment prompts.
It is not legal advice, production compliance certification, RBI approval,
NPCI approval, or bank integration evidence.

## Global honesty labels

- SOURCE_BACKED_REFERENCE
- OFFICIAL_SOURCE_REFERENCE
- MISSING_OFFICIAL_SOURCE
- SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL
- MOCK_BOUNDARY
- SYNTHETIC_DATA
- USER_PROVIDED_VALUE

## Source-backed references

### RBI_ODR_DIGITAL_PAYMENTS_2020

- Authority: Reserve Bank of India
- Title: Online Dispute Resolution (ODR) System for Digital Payments
- URL: https://www.rbi.org.in/commonman/english/scripts/Notification.aspx?Id=3194
- Publication date: 2020-08-06
- Freshness class: stable_circular_verify_before_release
- Source status: OFFICIAL_SOURCE_REFERENCE

Allowed usage:
- ODR concept modelling
- failed-transaction dispute scope
- rule-based system-driven design inspiration
- customer lodging and tracking design requirements
- data-minimisation and confidentiality design prompts

Prohibited usage:
- claiming actual ODR implementation
- claiming RBI approval or certification
- claiming production compliance
- using as legal advice

Extracted claims:
- SRC-ODR-001: RBI described ODR for digital-payment customer disputes as system-driven and rule-based, with zero or minimal manual intervention.
- SRC-ODR-002: The initial ODR scope covered disputes and grievances related to failed transactions.
- SRC-ODR-003: The ODR design expectation includes simple lodging, necessary minimum details, confidentiality, unique reference number, and tracking.

### RBI_FAILED_TRANSACTION_TAT_2019

- Authority: Reserve Bank of India
- Title: Harmonisation of Turn Around Time (TAT) and customer compensation for failed transactions using authorised Payment Systems
- URL: https://www.rbi.org.in/commonman/English/scripts/Notification.aspx?Id=3074
- Publication date: 2019-09-20
- Freshness class: stable_circular_verify_before_release
- Source status: OFFICIAL_SOURCE_REFERENCE

Allowed usage:
- failed-transaction definition
- UPI failed-transaction scenario modelling
- TAT and compensation awareness
- economics exposure modelling with source-backed labels

Prohibited usage:
- hard-coding live legal obligations without review
- claiming automated compensation is production-ready
- claiming bank-specific policy coverage

Extracted claims:
- SRC-TAT-001: RBI defined failed transactions to include cases not fully completed for reasons not attributable to the customer, including communication failure, timeout, non-credit to beneficiary, or delayed reversal.
- SRC-TAT-002: For UPI transfer of funds where the account is debited but the beneficiary account is not credited, the source lists auto-reversal by the beneficiary bank latest on T + 1 day and compensation if delay is beyond T + 1 day.
- SRC-TAT-003: For UPI merchant payment where the account is debited but transaction confirmation is not received at the merchant location, the source lists auto-reversal within T + 5 days and compensation if delay is beyond T + 5 days.

### RBI_LIMITED_LIABILITY_2017

- Authority: Reserve Bank of India
- Title: Customer Protection - Limiting Liability of Customers in Unauthorised Electronic Banking Transactions
- URL: https://www.rbi.org.in/commonman/english/scripts/Notification.aspx?Id=2336
- Publication date: 2017-07-06
- Freshness class: stable_circular_verify_before_release
- Source status: OFFICIAL_SOURCE_REFERENCE

Allowed usage:
- unauthorised-transaction escalation awareness
- customer reporting and acknowledgement design prompts
- customer-liability source-gap handling
- security and fraud-control quality prompts

Prohibited usage:
- treating fraud liability as same as failed UPI dispute
- automating legal liability decisions
- claiming bank-specific board-policy coverage

Extracted claims:
- SRC-LIAB-001: The source discusses customer notification timing, bank reporting channels, acknowledgement, and recording time/date of customer response for unauthorised electronic transactions.
- SRC-LIAB-002: The source states zero liability can arise in specified third-party breach circumstances when the customer notifies the bank within three working days.
- SRC-LIAB-003: The source states banks should resolve complaints and establish customer liability within timelines specified by board-approved policy, not exceeding 90 days.

### NPCI_UPI_PRODUCT_STATISTICS

- Authority: National Payments Corporation of India
- Title: Unified Payments Interface (UPI) Product Statistics
- URL: https://www.npci.org.in/product/upi/product-statistics
- Publication date: DYNAMIC_WEB_PAGE
- Freshness class: dynamic_verify_on_every_release
- Source status: OFFICIAL_DYNAMIC_SOURCE_REFERENCE

Allowed usage:
- current UPI volume/value source candidate
- capacity planning input when manually captured
- economics sensitivity analysis when date-stamped

Prohibited usage:
- embedding current transaction volume without capture date
- claiming live values from stale copied data
- using dynamic values without USER_PROVIDED_VALUE or source date

Extracted claims:
- SRC-NPCI-STATS-001: NPCI provides an official UPI product statistics page. Current volume and value figures are dynamic and must be captured with date, source URL, and review status.

### NPCI_COMPLAINT_STATUS

- Authority: National Payments Corporation of India
- Title: User Complaint Status
- URL: https://www.npci.org.in/complaint-status
- Publication date: DYNAMIC_WEB_PAGE
- Freshness class: dynamic_verify_before_demo_or_release
- Source status: OFFICIAL_DYNAMIC_SOURCE_REFERENCE

Allowed usage:
- complaint-status and tracking concept reference
- mock customer status-tracking design inspiration

Prohibited usage:
- calling the live NPCI complaint-status page
- submitting real complaint details
- claiming factory integration with NPCI

Extracted claims:
- SRC-NPCI-COMPLAINT-001: NPCI exposes a public complaint-status page, but the factory must model this only as a mock boundary.

### NPCI_UPI_PRODUCT_PAGE

- Authority: National Payments Corporation of India
- Title: UPI Product Page
- URL: https://www.npci.org.in/product/upi
- Publication date: DYNAMIC_WEB_PAGE
- Freshness class: dynamic_verify_before_demo_or_release
- Source status: OFFICIAL_DYNAMIC_SOURCE_REFERENCE

Allowed usage:
- UPI ecosystem orientation
- official NPCI product-page reference
- linking to UPI help and statistics source candidates

Prohibited usage:
- claiming live integration
- claiming current rules without circular evidence

Extracted claims:
- SRC-NPCI-UPI-001: NPCI maintains an official UPI product page that links to UPI statistics and customer help resources.

## Economics discipline

The registry may support economics reasoning only when the value is
source-backed, user-provided, or explicitly synthetic. Current UPI
volume/value, vendor prices, bank internal cost per dispute, staffing
cost, real ROI, penalty exposure, and real customer-impact values must
not be invented.

## Mock boundary

NPCI, RBI, bank, PSP, customer, ledger, notification, reconciliation,
and ODR integrations remain MOCK_BOUNDARY unless a future explicitly
approved production integration phase supplies real contracts and
authorization evidence.
