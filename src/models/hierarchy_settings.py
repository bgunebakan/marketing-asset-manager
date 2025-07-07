from dataclasses import dataclass
from typing import List


@dataclass
class HierarchyLevel:
    """Level in the folder hierarchy."""

    field: str
    position: int

    def __lt__(self, other):
        """Enable sorting by position."""
        if not isinstance(other, HierarchyLevel):
            return NotImplemented
        return self.position < other.position


@dataclass
class HierarchySettings:
    """Folder hierarchy configuration from Google Sheets."""

    levels: List[HierarchyLevel]

    def get_sorted_levels(self) -> List[HierarchyLevel]:
        """Get hierarchy levels sorted by position."""
        return sorted(self.levels)

    @classmethod
    def from_sheet_data(cls, data: List[List]) -> "HierarchySettings":
        """Create hierarchy settings from Google Sheet data.

        Expected format:
        level  | field
        -------|-------
        level_0| year
        level_1| country
        level_2| month
        level_3| audience
        """
        levels = []

        for row in data:
            if len(row) >= 2 and row[0] and row[1]:
                try:
                    # Extract position from level_X format or try direct conversion
                    if row[0].startswith("level_"):
                        position = int(row[0].split("_")[1])
                    else:
                        position = int(row[0])

                    field = row[1].lower().strip()
                    levels.append(HierarchyLevel(field=field, position=position))
                except (ValueError, TypeError, IndexError):
                    continue

        return cls(levels=levels)
