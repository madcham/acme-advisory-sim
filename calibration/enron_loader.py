"""
Enron Email Corpus Loader.

Loads and parses the Enron email dataset for behavioral exhaust calibration.
Extracts knowledge transfer patterns, exception handling discussions, and
organizational communication dynamics.

Dataset Source: CMU Enron Email Dataset
- https://www.cs.cmu.edu/~enron/
- 500,000+ emails from 150 senior Enron employees (1998-2002)

This loader supports both:
1. CSV preview format (from Kaggle/preprocessed sources)
2. Full maildir format (from CMU tar.gz)

Why Enron for Behavioral Exhaust:
- Real organizational hierarchy (senior → junior exchanges)
- Real tribal knowledge patterns
- Real exception handling discussions
- Real vendor/client relationship context
- Well-cited in academic literature (adds credibility)
"""

import csv
import re
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime
from pathlib import Path


@dataclass
class EnronEmail:
    """Parsed Enron email with extracted fields."""
    message_id: str
    date: Optional[datetime]
    from_email: str
    from_name: str
    to_email: str
    to_name: str
    subject: str
    body: str
    file_path: str

    # Derived fields
    from_username: str = ""
    to_username: str = ""

    def __post_init__(self):
        # Extract usernames from emails
        if self.from_email:
            match = re.match(r'([^@]+)@', self.from_email)
            self.from_username = match.group(1) if match else ""
        if self.to_email:
            match = re.match(r'([^@]+)@', self.to_email)
            self.to_username = match.group(1) if match else ""


@dataclass
class KnowledgeTransferPattern:
    """A knowledge transfer pattern extracted from email exchange."""
    pattern_type: str  # "question_answer", "instruction", "exception_warning", "process_explanation"
    from_person: str
    to_person: str
    subject_entity: Optional[str]  # vendor, client, process mentioned
    content: str
    confidence: float
    source_email_id: str

    # Pattern indicators found
    has_question: bool = False
    has_instruction: bool = False
    has_exception: bool = False
    has_approval_chain: bool = False


@dataclass
class EnronOrgProfile:
    """Organizational profile for an Enron employee."""
    email: str
    name: str
    username: str
    email_count: int = 0
    sent_count: int = 0
    received_count: int = 0
    # Inferred from communication patterns
    estimated_seniority: float = 0.5  # 0-1, higher = more senior
    departments_mentioned: Set[str] = field(default_factory=set)


class EnronLoader:
    """
    Loads and parses Enron email corpus.

    Supports CSV format (preview/Kaggle) and maildir format (full CMU dataset).
    """

    def __init__(self, data_path: str):
        """
        Initialize loader with path to data.

        Args:
            data_path: Path to CSV file or maildir directory
        """
        self.data_path = Path(data_path)
        self.emails: List[EnronEmail] = []
        self.profiles: Dict[str, EnronOrgProfile] = {}

        # Pattern detection regex
        self.question_patterns = [
            r'\?',
            r'can you',
            r'could you',
            r'would you',
            r'do you know',
            r'what is',
            r'how do',
            r'please send',
            r'please provide',
        ]

        self.instruction_patterns = [
            r'always\s+\w+',
            r'never\s+\w+',
            r'make sure',
            r'don\'t forget',
            r'remember to',
            r'you need to',
            r'you must',
            r'please ensure',
        ]

        self.exception_patterns = [
            r'except\s+',
            r'unless\s+',
            r'but not',
            r'don\'t\s+\w+\s+if',
            r'only if',
            r'special case',
            r'exception',
            r'override',
        ]

        self.approval_patterns = [
            r'cc\s+\w+',
            r'copy\s+\w+',
            r'get approval',
            r'needs? approval',
            r'sign off',
            r'authorized',
        ]

    def load(self) -> int:
        """
        Load emails from data source.

        Returns:
            Number of emails loaded
        """
        if self.data_path.suffix == '.csv':
            return self._load_csv()
        elif self.data_path.is_dir():
            return self._load_maildir()
        else:
            raise ValueError(f"Unsupported data format: {self.data_path}")

    def _load_csv(self) -> int:
        """Load from CSV format."""
        # Increase field size limit for large email bodies
        csv.field_size_limit(10 * 1024 * 1024)  # 10MB limit

        with open(self.data_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i == 0:
                    continue  # Skip header
                if len(row) >= 1:
                    email = self._parse_csv_row(row)
                    if email:
                        self.emails.append(email)
                        self._update_profile(email)

        # Calculate seniority estimates
        self._estimate_seniority()

        return len(self.emails)

    def _parse_csv_row(self, row: List[str]) -> Optional[EnronEmail]:
        """Parse a CSV row into an EnronEmail."""
        try:
            # CSV format varies:
            # - Full Kaggle format: row[0]=file, row[1]=message
            # - Preview format: row[0]=id, row[1]=file, row[2]=message
            # Check for Message-ID to identify the right column
            raw_content = ""
            file_path = ""
            for i, col in enumerate(row):
                if col and "Message-ID:" in col:
                    raw_content = col
                    # File path is typically in the column before the message
                    file_path = row[i - 1] if i > 0 else ""
                    break
            if not raw_content:
                return None

            # Extract fields using regex
            def extract(pattern: str) -> str:
                match = re.search(pattern, raw_content)
                return match.group(1).strip() if match else ""

            message_id = extract(r'Message-ID:\s*<([^>]+)>')
            date_str = extract(r'Date:\s*([^X]+?)(?=From:|$)')
            from_email = extract(r'From:\s*([^\s]+@[^\s]+)')
            to_email = extract(r'To:\s*([^\s]+@[^\s]+)')
            from_name = extract(r'X-From:\s*([^X]+?)(?=X-To:|$)')
            to_name = extract(r'X-To:\s*([^X<]+)')
            subject = extract(r'Subject:\s*([^M]+?)(?=Mime-Version:|$)')

            # Extract body - everything after X-FileName header value
            # The filename can have various formats: .pst, .nsf, (Non-Privileged).pst, etc.
            # Pattern: X-FileName: <filename>.<ext> <body_content>
            body_match = re.search(r'X-FileName:\s*\S+\.(?:pst|nsf)\s*(.+)', raw_content, re.DOTALL | re.IGNORECASE)
            body = body_match.group(1).strip() if body_match else ""

            # Parse date
            date = None
            if date_str:
                try:
                    # Format: Mon, 14 May 2001 16:39:00 -0700 (PDT)
                    date_clean = re.sub(r'\s*\([^)]+\)\s*', '', date_str).strip()
                    date = datetime.strptime(date_clean, '%a, %d %b %Y %H:%M:%S %z')
                except:
                    pass

            return EnronEmail(
                message_id=message_id,
                date=date,
                from_email=from_email.lower(),
                from_name=from_name.strip(),
                to_email=to_email.lower(),
                to_name=to_name.strip(),
                subject=subject.strip(),
                body=body,
                file_path=file_path,
            )
        except Exception as e:
            return None

    def _load_maildir(self) -> int:
        """Load from maildir format (full CMU dataset)."""
        # Walk the maildir structure
        for root, dirs, files in os.walk(self.data_path):
            for filename in files:
                if filename.startswith('.'):
                    continue
                filepath = Path(root) / filename
                email = self._parse_maildir_file(filepath)
                if email:
                    self.emails.append(email)
                    self._update_profile(email)

        self._estimate_seniority()
        return len(self.emails)

    def _parse_maildir_file(self, filepath: Path) -> Optional[EnronEmail]:
        """Parse a single maildir file."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Similar parsing to CSV but with proper line breaks
            headers = {}
            body_lines = []
            in_body = False

            for line in content.split('\n'):
                if not in_body:
                    if line.strip() == '':
                        in_body = True
                    elif ':' in line:
                        key, _, value = line.partition(':')
                        headers[key.strip()] = value.strip()
                else:
                    body_lines.append(line)

            return EnronEmail(
                message_id=headers.get('Message-ID', '').strip('<>'),
                date=None,  # Parse from headers if needed
                from_email=headers.get('From', '').lower(),
                from_name=headers.get('X-From', ''),
                to_email=headers.get('To', '').lower(),
                to_name=headers.get('X-To', ''),
                subject=headers.get('Subject', ''),
                body='\n'.join(body_lines),
                file_path=str(filepath),
            )
        except Exception:
            return None

    def _update_profile(self, email: EnronEmail) -> None:
        """Update organizational profile for sender and recipient."""
        # Update sender profile
        if email.from_email:
            if email.from_email not in self.profiles:
                self.profiles[email.from_email] = EnronOrgProfile(
                    email=email.from_email,
                    name=email.from_name,
                    username=email.from_username,
                )
            self.profiles[email.from_email].email_count += 1
            self.profiles[email.from_email].sent_count += 1

        # Update recipient profile
        if email.to_email:
            if email.to_email not in self.profiles:
                self.profiles[email.to_email] = EnronOrgProfile(
                    email=email.to_email,
                    name=email.to_name,
                    username=email.to_username,
                )
            self.profiles[email.to_email].email_count += 1
            self.profiles[email.to_email].received_count += 1

    def _estimate_seniority(self) -> None:
        """
        Estimate seniority based on communication patterns.

        Heuristics:
        - Higher sent/received ratio = more senior (gives more instructions)
        - More total emails = more central to org
        - Named in CC more often = more senior
        """
        if not self.profiles:
            return

        max_emails = max(p.email_count for p in self.profiles.values())

        for profile in self.profiles.values():
            # Normalize email count (0-0.4)
            volume_score = (profile.email_count / max_emails) * 0.4 if max_emails > 0 else 0

            # Sent/received ratio (0-0.4)
            total = profile.sent_count + profile.received_count
            if total > 0:
                ratio_score = (profile.sent_count / total) * 0.4
            else:
                ratio_score = 0.2

            # Base score (0.2)
            base_score = 0.2

            profile.estimated_seniority = min(1.0, volume_score + ratio_score + base_score)

    def extract_knowledge_patterns(self) -> List[KnowledgeTransferPattern]:
        """
        Extract knowledge transfer patterns from loaded emails.

        Returns:
            List of KnowledgeTransferPattern objects
        """
        patterns = []

        for email in self.emails:
            if not email.body or len(email.body) < 20:
                continue

            body_lower = email.body.lower()

            # Detect pattern types
            has_question = any(re.search(p, body_lower) for p in self.question_patterns)
            has_instruction = any(re.search(p, body_lower) for p in self.instruction_patterns)
            has_exception = any(re.search(p, body_lower) for p in self.exception_patterns)
            has_approval = any(re.search(p, body_lower) for p in self.approval_patterns)

            # Determine pattern type
            if has_instruction and has_exception:
                pattern_type = "exception_warning"
                confidence = 0.85
            elif has_instruction:
                pattern_type = "instruction"
                confidence = 0.75
            elif has_question:
                pattern_type = "question_answer"
                confidence = 0.70
            elif has_approval:
                pattern_type = "approval_chain"
                confidence = 0.80
            else:
                continue  # Skip emails without clear patterns

            # Extract subject entity (simplified)
            subject_entity = None
            entity_patterns = [
                r'(\w+\s+(?:inc|corp|llc|ltd|company|group|partners))',
                r'(project\s+\w+)',
                r'(deal\s+\w+)',
            ]
            for ep in entity_patterns:
                match = re.search(ep, body_lower)
                if match:
                    subject_entity = match.group(1).title()
                    break

            patterns.append(KnowledgeTransferPattern(
                pattern_type=pattern_type,
                from_person=email.from_name or email.from_username,
                to_person=email.to_name or email.to_username,
                subject_entity=subject_entity,
                content=email.body[:500],  # Truncate for storage
                confidence=confidence,
                source_email_id=email.message_id,
                has_question=has_question,
                has_instruction=has_instruction,
                has_exception=has_exception,
                has_approval_chain=has_approval,
            ))

        return patterns

    def get_senior_junior_exchanges(
        self,
        seniority_threshold: float = 0.2,
    ) -> List[Tuple[EnronEmail, float]]:
        """
        Get emails where a senior person is communicating to a junior person.

        Args:
            seniority_threshold: Minimum seniority difference to consider

        Returns:
            List of (email, seniority_gap) tuples
        """
        exchanges = []

        for email in self.emails:
            from_profile = self.profiles.get(email.from_email)
            to_profile = self.profiles.get(email.to_email)

            if not from_profile or not to_profile:
                continue

            seniority_gap = from_profile.estimated_seniority - to_profile.estimated_seniority

            if seniority_gap >= seniority_threshold:
                exchanges.append((email, seniority_gap))

        # Sort by seniority gap (most senior to most junior first)
        exchanges.sort(key=lambda x: x[1], reverse=True)

        return exchanges

    def get_statistics(self) -> Dict[str, any]:
        """Get statistics about loaded data."""
        return {
            "total_emails": len(self.emails),
            "unique_senders": len(set(e.from_email for e in self.emails if e.from_email)),
            "unique_recipients": len(set(e.to_email for e in self.emails if e.to_email)),
            "profiles_created": len(self.profiles),
            "emails_with_body": len([e for e in self.emails if e.body]),
            "date_range": self._get_date_range(),
        }

    def _get_date_range(self) -> Tuple[Optional[str], Optional[str]]:
        """Get min and max dates in dataset."""
        dates = [e.date for e in self.emails if e.date]
        if not dates:
            return (None, None)
        return (min(dates).isoformat(), max(dates).isoformat())


def load_enron_dataset(path: str) -> EnronLoader:
    """
    Convenience function to load Enron dataset.

    Args:
        path: Path to CSV file or maildir directory

    Returns:
        Loaded EnronLoader instance
    """
    loader = EnronLoader(path)
    count = loader.load()
    print(f"Loaded {count} emails from Enron dataset")
    return loader
