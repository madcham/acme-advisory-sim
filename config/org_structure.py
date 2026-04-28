"""
Organizational structure for Acme Advisory.

Defines the company profile, departments, roles, headcount, and tenure distribution
that drive the simulation's behavioral patterns.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict
import random


class TenureBand(str, Enum):
    """Tenure bands affecting institutional knowledge signal."""
    UNDER_1_YEAR = "under_1_year"
    ONE_TO_THREE = "1_to_3_years"
    THREE_TO_SEVEN = "3_to_7_years"
    OVER_7_YEARS = "over_7_years"


class Role(str, Enum):
    """Staff roles with different behavioral patterns."""
    CONSULTANT = "consultant"
    SENIOR_CONSULTANT = "senior_consultant"
    MANAGER = "manager"
    SENIOR_MANAGER = "senior_manager"
    PRINCIPAL = "principal"
    PARTNER = "partner"
    DEPARTMENT_HEAD = "department_head"
    CEO = "ceo"


@dataclass
class StaffMember:
    """Represents an individual staff member."""
    id: str
    name: str
    department: str
    role: Role
    tenure_band: TenureBand
    tenure_years: float
    is_department_head: bool = False
    special_flags: List[str] = None

    def __post_init__(self):
        if self.special_flags is None:
            self.special_flags = []

    @property
    def institutional_knowledge_weight(self) -> float:
        """Weight for behavioral exhaust signal based on tenure."""
        weights = {
            TenureBand.UNDER_1_YEAR: 0.2,
            TenureBand.ONE_TO_THREE: 0.5,
            TenureBand.THREE_TO_SEVEN: 0.8,
            TenureBand.OVER_7_YEARS: 1.0,
        }
        return weights[self.tenure_band]


COMPANY_PROFILE = {
    "name": "Acme Advisory",
    "type": "Mid-market management consulting and advisory firm",
    "size": 90,
    "revenue_model": "Project-based engagements, retainer clients, occasional subcontracting",
    "target_utilization": 0.72,  # 72% billable utilization target
}

TENURE_DISTRIBUTION = {
    TenureBand.UNDER_1_YEAR: 0.20,   # 20% under 1 year
    TenureBand.ONE_TO_THREE: 0.40,   # 40% 1-3 years
    TenureBand.THREE_TO_SEVEN: 0.30, # 30% 3-7 years
    TenureBand.OVER_7_YEARS: 0.10,   # 10% over 7 years
}

DEPARTMENTS = {
    "client_delivery": {
        "name": "Client Delivery",
        "head": "Sarah Chen",
        "head_id": "sarah_chen",
        "headcount": 35,
        "primary_function": "Engagement execution, deliverable production",
        "role_distribution": {
            Role.CONSULTANT: 0.35,
            Role.SENIOR_CONSULTANT: 0.30,
            Role.MANAGER: 0.20,
            Role.SENIOR_MANAGER: 0.10,
            Role.PRINCIPAL: 0.05,
        }
    },
    "business_development": {
        "name": "Business Development",
        "head": "Marcus Webb",
        "head_id": "marcus_webb",
        "headcount": 15,
        "primary_function": "Proposals, pipeline, client relationships",
        "role_distribution": {
            Role.CONSULTANT: 0.20,
            Role.SENIOR_CONSULTANT: 0.25,
            Role.MANAGER: 0.25,
            Role.SENIOR_MANAGER: 0.20,
            Role.PARTNER: 0.10,
        }
    },
    "talent_staffing": {
        "name": "Talent and Staffing",
        "head": "Priya Nair",
        "head_id": "priya_nair",
        "headcount": 10,
        "primary_function": "Resourcing, hiring, utilization management",
        "role_distribution": {
            Role.CONSULTANT: 0.30,
            Role.SENIOR_CONSULTANT: 0.30,
            Role.MANAGER: 0.30,
            Role.SENIOR_MANAGER: 0.10,
        }
    },
    "finance_operations": {
        "name": "Finance and Operations",
        "head": "David Okafor",
        "head_id": "david_okafor",
        "headcount": 12,
        "primary_function": "Billing, contracts, vendor management, P&L",
        "role_distribution": {
            Role.CONSULTANT: 0.25,
            Role.SENIOR_CONSULTANT: 0.35,
            Role.MANAGER: 0.25,
            Role.SENIOR_MANAGER: 0.15,
        }
    },
    "knowledge_management": {
        "name": "Knowledge Management",
        "head": "Elena Vasquez",
        "head_id": "elena_vasquez",
        "headcount": 8,
        "primary_function": "IP capture, methodology, tools",
        "role_distribution": {
            Role.CONSULTANT: 0.25,
            Role.SENIOR_CONSULTANT: 0.40,
            Role.MANAGER: 0.25,
            Role.SENIOR_MANAGER: 0.10,
        }
    },
    "executive_leadership": {
        "name": "Executive Leadership",
        "head": "James Holloway",
        "head_id": "james_holloway",
        "headcount": 10,
        "primary_function": "Strategy, major client relationships, escalations",
        "role_distribution": {
            Role.SENIOR_MANAGER: 0.30,
            Role.PRINCIPAL: 0.40,
            Role.PARTNER: 0.30,
        }
    },
}

# Organizational dynamics that create realistic chaos
ORG_DYNAMICS = {
    "utilization_pressure": {
        "target": 0.72,
        "conflict_threshold": 0.68,  # Below this triggers staffing conflicts
        "description": "Acme targets 72% billable utilization. Below threshold triggers conflict.",
    },
    "partner_politics": {
        "competing_partners": ["marcus_webb", "sarah_chen"],
        "description": "Two senior partners have competing views on client prioritization.",
    },
    "knowledge_hoarding": {
        "key_holders": ["principal_1", "principal_2", "principal_3"],
        "description": "Three long-tenure principals hold critical client relationship context informally.",
    },
    "subcontractor_dependency": {
        "key_vendors": ["brightline_consulting", "vance_analytics"],
        "description": "Two key subcontractors have complex pricing histories and relationship baggage.",
    },
    "scope_creep_pattern": {
        "affected_vertical": "financial_services",
        "description": "FS clients expand scope verbally before formalizing, creating billing disputes.",
    },
}

# Key individuals referenced in seeded context
KEY_INDIVIDUALS = {
    "james_holloway": StaffMember(
        id="james_holloway",
        name="James Holloway",
        department="executive_leadership",
        role=Role.CEO,
        tenure_band=TenureBand.OVER_7_YEARS,
        tenure_years=12.0,
        is_department_head=True,
        special_flags=["ceo", "write_off_approver"]
    ),
    "sarah_chen": StaffMember(
        id="sarah_chen",
        name="Sarah Chen",
        department="client_delivery",
        role=Role.DEPARTMENT_HEAD,
        tenure_band=TenureBand.OVER_7_YEARS,
        tenure_years=8.5,
        is_department_head=True,
        special_flags=["partner", "delivery_head"]
    ),
    "marcus_webb": StaffMember(
        id="marcus_webb",
        name="Marcus Webb",
        department="business_development",
        role=Role.DEPARTMENT_HEAD,
        tenure_band=TenureBand.OVER_7_YEARS,
        tenure_years=9.0,
        is_department_head=True,
        special_flags=["partner", "hartwell_relationship"]
    ),
    "priya_nair": StaffMember(
        id="priya_nair",
        name="Priya Nair",
        department="talent_staffing",
        role=Role.DEPARTMENT_HEAD,
        tenure_band=TenureBand.THREE_TO_SEVEN,
        tenure_years=5.5,
        is_department_head=True,
        special_flags=["staffing_authority", "72hr_notice_required"]
    ),
    "david_okafor": StaffMember(
        id="david_okafor",
        name="David Okafor",
        department="finance_operations",
        role=Role.DEPARTMENT_HEAD,
        tenure_band=TenureBand.THREE_TO_SEVEN,
        tenure_years=6.0,
        is_department_head=True,
        special_flags=["vendor_approver", "brightline_secondary_approval"]
    ),
    "elena_vasquez": StaffMember(
        id="elena_vasquez",
        name="Elena Vasquez",
        department="knowledge_management",
        role=Role.DEPARTMENT_HEAD,
        tenure_band=TenureBand.THREE_TO_SEVEN,
        tenure_years=4.5,
        is_department_head=True,
        special_flags=["fs_methodology_holder"]
    ),
    "jordan_park": StaffMember(
        id="jordan_park",
        name="Jordan Park",
        department="client_delivery",
        role=Role.SENIOR_CONSULTANT,
        tenure_band=TenureBand.ONE_TO_THREE,
        tenure_years=2.5,
        special_flags=["nexum_conflict"]
    ),
}


def _generate_staff_pool(seed: int = 42) -> List[StaffMember]:
    """Generate the full staff pool based on org structure."""
    random.seed(seed)
    staff = list(KEY_INDIVIDUALS.values())
    staff_id_counter = 1

    # First names and last names for generation
    first_names = [
        "Alex", "Morgan", "Taylor", "Jordan", "Casey", "Riley", "Quinn", "Avery",
        "Cameron", "Drew", "Jamie", "Kelly", "Lee", "Pat", "Sam", "Chris",
        "Dana", "Kim", "Lynn", "Robin", "Terry", "Tracy", "Val", "Skyler",
        "Reese", "Parker", "Hayden", "Emery", "Finley", "Harper", "Blake", "Rowan",
        "Sage", "River", "Phoenix", "Dakota", "Kendall", "Logan", "Bailey", "Peyton"
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
        "Rodriguez", "Martinez", "Anderson", "Taylor", "Thomas", "Moore", "Jackson",
        "Martin", "Lee", "Thompson", "White", "Harris", "Clark", "Lewis", "Robinson",
        "Walker", "Young", "King", "Wright", "Scott", "Green", "Baker", "Adams",
        "Nelson", "Hill", "Campbell", "Mitchell", "Roberts", "Carter", "Phillips", "Evans"
    ]

    existing_ids = set(KEY_INDIVIDUALS.keys())

    for dept_key, dept in DEPARTMENTS.items():
        # Subtract department heads already in KEY_INDIVIDUALS
        heads_in_dept = sum(1 for s in KEY_INDIVIDUALS.values() if s.department == dept_key)
        remaining = dept["headcount"] - heads_in_dept

        for _ in range(remaining):
            # Assign tenure band based on distribution
            tenure_roll = random.random()
            cumulative = 0
            tenure_band = TenureBand.UNDER_1_YEAR
            for band, prob in TENURE_DISTRIBUTION.items():
                cumulative += prob
                if tenure_roll <= cumulative:
                    tenure_band = band
                    break

            # Calculate actual tenure years within band
            tenure_ranges = {
                TenureBand.UNDER_1_YEAR: (0.1, 0.99),
                TenureBand.ONE_TO_THREE: (1.0, 2.99),
                TenureBand.THREE_TO_SEVEN: (3.0, 6.99),
                TenureBand.OVER_7_YEARS: (7.0, 15.0),
            }
            tenure_years = random.uniform(*tenure_ranges[tenure_band])

            # Assign role based on department distribution
            role_roll = random.random()
            cumulative = 0
            role = Role.CONSULTANT
            for r, prob in dept["role_distribution"].items():
                cumulative += prob
                if role_roll <= cumulative:
                    role = r
                    break

            # Generate unique name
            while True:
                name = f"{random.choice(first_names)} {random.choice(last_names)}"
                staff_id = name.lower().replace(" ", "_")
                if staff_id not in existing_ids:
                    existing_ids.add(staff_id)
                    break

            staff.append(StaffMember(
                id=staff_id,
                name=name,
                department=dept_key,
                role=role,
                tenure_band=tenure_band,
                tenure_years=round(tenure_years, 1),
            ))
            staff_id_counter += 1

    return staff


# Generate staff pool on module load
_STAFF_POOL: List[StaffMember] = _generate_staff_pool()


def get_all_staff() -> List[StaffMember]:
    """Return all staff members."""
    return _STAFF_POOL.copy()


def get_department_staff(department: str) -> List[StaffMember]:
    """Return staff members in a specific department."""
    return [s for s in _STAFF_POOL if s.department == department]


def get_staff_by_tenure(tenure_band: TenureBand) -> List[StaffMember]:
    """Return staff members in a specific tenure band."""
    return [s for s in _STAFF_POOL if s.tenure_band == tenure_band]


def get_staff_by_role(role: Role) -> List[StaffMember]:
    """Return staff members with a specific role."""
    return [s for s in _STAFF_POOL if s.role == role]


def get_staff_by_id(staff_id: str) -> StaffMember:
    """Return a specific staff member by ID."""
    for s in _STAFF_POOL:
        if s.id == staff_id:
            return s
    raise ValueError(f"Staff member not found: {staff_id}")
