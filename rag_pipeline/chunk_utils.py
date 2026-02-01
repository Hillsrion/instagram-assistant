from typing import List
def repeat_with_budget(items: List[str], total_budget: int) -> List[str]:
    if not items:
        return []
    repeat = max(1, total_budget // len(items))
    return [item for item in items for _ in range(repeat)]