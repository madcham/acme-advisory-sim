# Nomenclature Guide: Intuitive Naming Convention

## Principle

Every name should be self-documenting. A new user looking at the simulation should immediately understand:
- What entity they're looking at
- What it does or what rule it encodes
- Why it matters

**Rule:** If you have to explain what a name means, rename it.

---

## Current vs Proposed Names

### Agents (AI Systems)

| Current | Proposed | Role |
|---------|----------|------|
| `vendor_agent` | `Procurement AI` | Handles vendor contracts, SOWs, approvals |
| `billing_agent` | `Accounts Receivable AI` | Manages invoicing, collections, payment tracking |
| `proposal_agent` | `Business Development AI` | Creates proposals, handles go/no-go decisions |
| `staffing_agent` | `Resource Management AI` | Assigns staff to projects, manages allocations |

### Departments / Workflows

| Current ID | Proposed Name | What It Covers |
|------------|---------------|----------------|
| W1 | Client Engagements | Active project delivery, scope management |
| W2 | Business Development | Proposals, pipeline, go/no-go decisions |
| W3 | Resource Management | Staff allocation, scheduling, capacity |
| W4 | Vendor & Procurement | Contracts, SOWs, vendor relationships |
| W5 | Finance & Billing | Invoices, collections, write-offs |

### Context Objects (Institutional Knowledge)

Each context object should have a clear, self-documenting payload. The ID (CTX-001) is for machines; the description is for humans.

| ID | Current Reference | Proposed Display Name | One-Line Summary |
|----|-------------------|----------------------|------------------|
| CTX-001 | "Brightline SOW" | **Overbilling Vendor: Secondary Approval Required** | Brightline overbilled 40% in 2022 → Require Finance Director approval |
| CTX-002 | "FS scope creep" | **Financial Services Clients: Document Scope Changes** | FS clients expand scope verbally in weeks 3-4 → Document within 24 hours |
| CTX-003 | "Hartwell override" | **Partner Override: Hartwell Group Exception** | Marcus Webb always approves Hartwell regardless of margin |
| CTX-004 | "Priya notice" | **Senior Staff Reallocation: 72-Hour Notice** | Priya Nair requires 72-hour notice before moving senior resources |
| CTX-005 | "Vance pricing" | **Vendor Discount: Vance Analytics Negotiation** | Vance Analytics offers 15% discount on $500K+ engagements |
| CTX-006 | "TerraLogic payment" | **Client Payment Cycle: TerraLogic 60-Day Rule** | TerraLogic always pays at 60 days → Don't escalate before day 65 |
| CTX-007 | "COI check" | **Compliance: Former Employee Conflict Check** | Manual COI check required when former staff work at client |
| CTX-008 | "Elena FS methodology" | **Subject Matter Expert: Financial Services** | Elena Vasquez holds undocumented FS methodology → Consult directly |
| CTX-009 | "Write-off threshold" | **CEO Approval: Write-offs Above $15K** | Write-offs over $15K require CEO approval (verbal policy) |
| CTX-010 | "Jordan Park conflict" | **Staff-Client Conflict: Jordan Park / Nexum** | Jordan Park cannot be assigned to Nexum Partners (HR conflict) |
| CTX-011 | "Friday submissions" | **[EXPIRED] Friday Proposal Timing** | Old observation about Friday win rates — no longer reliable |
| CTX-012 | "50-page review" | **[EXPIRED] Partner Review Threshold** | Old 50-page review rule — now only applies to regulatory submissions |

### Scenarios (Test Cases)

| Current | Proposed | What It Tests |
|---------|----------|---------------|
| `brightline_sow` | `overbilling_vendor_approval` | Does agent know to get secondary approval? |
| `jordan_park_staffing` | `staff_client_conflict` | Does agent know Jordan can't work with Nexum? |
| `terralogic_payment` | `client_payment_cycle` | Does agent know not to escalate before day 65? |
| `hartwell_proposal` | `partner_override_exception` | Does agent know Marcus will approve Hartwell? |

### People (Staff & Stakeholders)

| Name | Role | Why They Matter |
|------|------|-----------------|
| David Okafor | Finance Director | Required approver for Brightline vendor |
| Marcus Webb | Senior Partner | Overrides go/no-go for Hartwell Group |
| Priya Nair | HR Director | Requires 72-hour notice for staff changes |
| Elena Vasquez | FS Practice Lead | Holds undocumented methodology knowledge |
| James Holloway | CEO | Verbal policy on $15K write-off threshold |
| Jordan Park | Consultant | Documented conflict with Nexum Partners |

### Clients

| Name | Key Characteristic | Associated Knowledge |
|------|-------------------|---------------------|
| TerraLogic | 60-day payment cycle | Don't escalate before day 65 |
| Hartwell Group | Partner override | Marcus Webb always approves |
| Nexum Partners | Staff conflict | Jordan Park cannot be assigned |

### Vendors

| Name | Key Characteristic | Associated Knowledge |
|------|-------------------|---------------------|
| Brightline Consulting | Overbilling history | Requires secondary approval |
| Vance Analytics | Negotiable pricing | 15% discount on $500K+ |

---

## UI Display Guidelines

### In Context Objects

Instead of showing:
```
CTX-001: Brightline Consulting always requires secondary approval...
```

Show:
```
🏛️ INSTITUTIONAL KNOWLEDGE

Overbilling Vendor: Secondary Approval Required
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Brightline Consulting overbilled 40% in 2022 on a federal engagement.

RULE: Always get Finance Director (David Okafor) approval before
      signing any Brightline SOW.

Reliability: 91% │ Source: Failure Recovery │ Decay: Milestone-based
```

### In Scenarios

Instead of:
```
Scenario: brightline_sow
Type: vendor_sow
```

Show:
```
🔴 HIGH-RISK SCENARIO

Overbilling Vendor Seeking New Contract
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SITUATION: Brightline Consulting submitted a new SOW for $180K.

WHAT THE AGENT NEEDS TO KNOW:
This vendor overbilled us 40% in 2022. Finance Director approval required.

✅ CORRECT: Route to David Okafor for secondary approval
❌ WRONG: Approve based on current terms alone
```

### In Decision History

Instead of:
```
Week 3: vendor_sow (incorrect)
Context Used: CTX-001
```

Show:
```
❌ Week 3: Overbilling Vendor Approval
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DECISION: Approved Brightline SOW without secondary sign-off

WHY IT'S WRONG: This vendor has a history of overbilling.
Finance Director approval is required per institutional knowledge.

KNOWLEDGE AVAILABLE: Yes — "Overbilling Vendor: Secondary Approval Required"
KNOWLEDGE USED: No — Agent did not retrieve or apply this rule
```

---

## Naming Patterns

### For Rules/Policies
`[Category]: [What] + [Requirement]`
- "Overbilling Vendor: Secondary Approval Required"
- "Senior Staff Reallocation: 72-Hour Notice"
- "Client Payment Cycle: TerraLogic 60-Day Rule"

### For Exceptions
`[Who/What] Exception: [Rule Override]`
- "Partner Override: Hartwell Group Exception"
- "CEO Approval: Write-offs Above $15K"

### For Conflicts/Warnings
`[Entity]-[Entity] Conflict: [Nature]`
- "Staff-Client Conflict: Jordan Park / Nexum"
- "Vendor Risk: Brightline Overbilling History"

### For Expired/Deprecated
`[EXPIRED] [Original Name]`
- "[EXPIRED] Friday Proposal Timing"
- "[EXPIRED] Partner Review Threshold"

---

## Implementation Checklist

- [ ] Rename agent IDs in `config/simulation_config.py`
- [ ] Update scenario names in `generators/agent_exhaust.py`
- [ ] Add display names to context objects in `config/seeded_context.py`
- [ ] Update UI to show display names instead of IDs
- [ ] Update all references in app.py
- [ ] Update test fixtures if any

---

*This document defines the naming convention for the Context Bank simulation. All new entities should follow these patterns.*
