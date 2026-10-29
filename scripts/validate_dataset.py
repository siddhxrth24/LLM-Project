#!/usr/bin/env python3
"""Validate a JSONL training dataset for SemesTrack fine-tuning.

Checks:
- File exists and is valid JSONL
- Each line has required fields: instruction, output
- Optional field: input
- No empty instruction or output
- Reasonable length limits
- Valid JSON on each line
- Reports statistics
"""

import argparse
import json
import sys
from pathlib import Path


def validate_dataset(filepath: str, max_instruction_len: int = 2048, max_output_len: int = 4096) -> bool:
    """Validate a JSONL training dataset.
    
    Args:
        filepath: Path to the .jsonl file
        max_instruction_len: Maximum instruction length in characters
        max_output_len: Maximum output length in characters
        
    Returns:
        True if valid, False if errors found
    """
    path = Path(filepath)
    
    if not path.exists():
        print(f"ERROR: File not found: {filepath}")
        return False
    
    if not path.suffix == ".jsonl":
        print(f"WARNING: File extension is '{path.suffix}', expected '.jsonl'")
    
    errors = []
    warnings = []
    stats = {
        "total_lines": 0,
        "valid_lines": 0,
        "with_input": 0,
        "avg_instruction_len": 0,
        "avg_output_len": 0,
        "min_output_len": float("inf"),
        "max_output_len": 0,
        "task_types": {"definition": 0, "classification": 0, "planning": 0, "other": 0},
    }
    
    instruction_lens = []
    output_lens = []
    
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            stats["total_lines"] += 1
            line = line.strip()
            
            if not line:
                warnings.append(f"Line {line_num}: Empty line")
                continue
            
            # Parse JSON
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: Invalid JSON - {e}")
                continue
            
            # Check required fields
            if not isinstance(data, dict):
                errors.append(f"Line {line_num}: Expected JSON object, got {type(data).__name__}")
                continue
            
            if "instruction" not in data:
                errors.append(f"Line {line_num}: Missing 'instruction' field")
                continue
            
            if "output" not in data:
                errors.append(f"Line {line_num}: Missing 'output' field")
                continue
            
            instruction = data["instruction"]
            output = data["output"]
            input_text = data.get("input", "")
            
            # Check types
            if not isinstance(instruction, str):
                errors.append(f"Line {line_num}: 'instruction' must be a string")
                continue
            
            if not isinstance(output, str):
                errors.append(f"Line {line_num}: 'output' must be a string")
                continue
            
            # Check non-empty
            if not instruction.strip():
                errors.append(f"Line {line_num}: Empty instruction")
                continue
            
            if not output.strip():
                errors.append(f"Line {line_num}: Empty output")
                continue
            
            # Check lengths
            if len(instruction) > max_instruction_len:
                warnings.append(
                    f"Line {line_num}: Instruction length ({len(instruction)}) "
                    f"exceeds {max_instruction_len}"
                )
            
            if len(output) > max_output_len:
                warnings.append(
                    f"Line {line_num}: Output length ({len(output)}) "
                    f"exceeds {max_output_len}"
                )
            
            # Check for unexpected fields
            known_fields = {"instruction", "input", "output"}
            unknown = set(data.keys()) - known_fields
            if unknown:
                warnings.append(f"Line {line_num}: Unknown fields: {unknown}")
            
            # Classify task type
            instr_lower = instruction.lower()
            if "define" in instr_lower or "definition" in instr_lower:
                stats["task_types"]["definition"] += 1
            elif "classify" in instr_lower or "coverage" in instr_lower:
                stats["task_types"]["classification"] += 1
            elif "plan" in instr_lower or "schedule" in instr_lower or "study" in instr_lower:
                stats["task_types"]["planning"] += 1
            else:
                stats["task_types"]["other"] += 1
            
            # Update stats
            stats["valid_lines"] += 1
            if input_text.strip():
                stats["with_input"] += 1
            
            instruction_lens.append(len(instruction))
            output_lens.append(len(output))
            stats["min_output_len"] = min(stats["min_output_len"], len(output))
            stats["max_output_len"] = max(stats["max_output_len"], len(output))
    
    # Calculate averages
    if instruction_lens:
        stats["avg_instruction_len"] = sum(instruction_lens) / len(instruction_lens)
    if output_lens:
        stats["avg_output_len"] = sum(output_lens) / len(output_lens)
    
    # Print results
    print(f"\n{'='*60}")
    print(f"Dataset Validation Report: {filepath}")
    print(f"{'='*60}")
    print(f"\nStatistics:")
    print(f"  Total lines:           {stats['total_lines']}")
    print(f"  Valid examples:        {stats['valid_lines']}")
    print(f"  With input field:      {stats['with_input']}")
    print(f"  Avg instruction len:   {stats['avg_instruction_len']:.0f} chars")
    print(f"  Avg output len:        {stats['avg_output_len']:.0f} chars")
    print(f"  Min output len:        {stats['min_output_len']} chars")
    print(f"  Max output len:        {stats['max_output_len']} chars")
    print(f"\nTask Type Distribution:")
    for task_type, count in stats["task_types"].items():
        print(f"  {task_type:20s}: {count}")
    
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings[:20]:
            print(f"  ⚠ {w}")
        if len(warnings) > 20:
            print(f"  ... and {len(warnings) - 20} more")
    
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors[:20]:
            print(f"  ✗ {e}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        print(f"\nResult: FAILED ✗")
        return False
    else:
        print(f"\nResult: PASSED ✓")
        return True


def main():
    parser = argparse.ArgumentParser(description="Validate JSONL training dataset for SemesTrack")
    parser.add_argument("filepath", help="Path to the .jsonl file")
    parser.add_argument("--max-instruction-len", type=int, default=2048, help="Max instruction length")
    parser.add_argument("--max-output-len", type=int, default=4096, help="Max output length")
    args = parser.parse_args()
    
    success = validate_dataset(args.filepath, args.max_instruction_len, args.max_output_len)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
