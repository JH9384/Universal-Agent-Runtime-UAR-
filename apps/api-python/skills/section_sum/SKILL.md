# section_sum

## Intent
Sum numeric values within a document section.

## Behavior
- Input: numeric values extracted from a section
- Output: single aggregated value (sum)

## Strategy Notes
- Preferred when goal is maximize total
- Competes with max_contents and min_contents depending on goal

## Example
Input: [5, 10]
Output: 15

## Learning
If this skill consistently wins for goal=maximize, increase its priority in strategy selection.
