# Project Content Creation Instructions

> Instructions for creating learning project content for SQL, Python, and Cybersecurity workspaces.

---

## Overview

Each project is a JSON file that defines a hierarchical learning path. Projects are ingested into the LTT database and used by the AI tutor to guide learners.

**Project Types**:
- `sql` - SQL workspace with in-browser SQLite
- `python` - Python workspace with in-browser Pyodide
- `cybersecurity` - Terminal workspace with SSH to sandboxes

---

## JSON Schema

```json
{
  "title": "Project Title",
  "description": "What the learner will build/learn",
  "workspace_type": "sql | python | cybersecurity",
  "narrative_context": "Real-world story/motivation",
  "learning_objectives": [
    {"level": "apply", "description": "Bloom's level objective"}
  ],
  "content": "## Markdown introduction content",
  "epics": [
    {
      "title": "Epic Title",
      "description": "Feature area description",
      "tasks": [
        {
          "title": "Task Title",
          "description": "Specific work unit",
          "acceptance_criteria": "- Criterion 1\n- Criterion 2",
          "tutor_guidance": {
            "teaching_approach": "How to teach this",
            "hints_to_give": ["Hint 1", "Hint 2"],
            "common_mistakes": ["Mistake 1"],
            "answer_rationale": "Why the answer works"
          },
          "subtasks": [
            {
              "title": "Subtask Title",
              "description": "Atomic work item",
              "acceptance_criteria": "...",
              "validation": {
                "type": "validation_type",
                "expected": { ... }
              },
              "tutor_guidance": { ... }
            }
          ]
        }
      ]
    }
  ]
}
```

---

## Validation Types by Workspace

### SQL Workspace

```json
{
  "validation": {
    "type": "sql",
    "expected": {
      "query_contains": ["SELECT", "WHERE"],
      "result_row_count": 5,
      "result_contains": ["value1", "value2"]
    }
  }
}
```

### Python Workspace

```json
{
  "validation": {
    "type": "python_output",
    "expected": {
      "output_contains": ["Hello, World!"],
      "output_matches": "^\\d+$",
      "no_errors": true
    }
  }
}
```

### Cybersecurity Workspace

```json
// Flag capture
{
  "validation": {
    "type": "flag_capture",
    "expected": {
      "flag": "FLAG{example_flag_here}"
    }
  }
}

// Command validation
{
  "validation": {
    "type": "terminal_command",
    "expected": {
      "command_pattern": "ls\\s+-la",
      "output_contains": [".bashrc"]
    }
  }
}
```

---

## Tutor Guidance Best Practices

### teaching_approach
- Describe HOW to teach, not WHAT to teach
- Reference pedagogical techniques (Socratic, scaffolding, etc.)
- Consider learner's likely prior knowledge

### hints_to_give
- Order from subtle to explicit
- First hints should nudge, not reveal
- Last hint can be nearly the answer

### common_mistakes
- List actual mistakes learners make
- Include syntax errors, conceptual errors
- Helps tutor recognize and address issues

### answer_rationale
- Explain WHY the correct answer works
- Connect to underlying concepts
- Useful for tutor's explanations

---

## Example: Python Basics Project

```json
{
  "title": "Python Programming Fundamentals",
  "description": "Learn Python basics through hands-on coding exercises",
  "workspace_type": "python",
  "narrative_context": "You're building a toolkit of Python skills that will help you automate tasks and analyze data.",
  "learning_objectives": [
    {"level": "remember", "description": "Recall Python syntax for variables, loops, and functions"},
    {"level": "apply", "description": "Write Python programs that solve basic problems"}
  ],
  "epics": [
    {
      "title": "Getting Started with Python",
      "description": "Your first Python programs",
      "tasks": [
        {
          "title": "Hello World",
          "description": "Write your first Python program",
          "subtasks": [
            {
              "title": "Print a message",
              "description": "Use the print() function to display text",
              "acceptance_criteria": "- Use print() function\n- Display: Hello, World!",
              "validation": {
                "type": "python_output",
                "expected": {
                  "output_contains": ["Hello, World!"]
                }
              },
              "tutor_guidance": {
                "teaching_approach": "Start with the simplest possible program. Let them experiment.",
                "hints_to_give": [
                  "Python uses print() to display text",
                  "Text needs to be wrapped in quotes",
                  "Try: print(\"Hello, World!\")"
                ],
                "common_mistakes": [
                  "Forgetting quotes around text",
                  "Using Print() instead of print()",
                  "Missing parentheses"
                ]
              }
            }
          ]
        }
      ]
    }
  ]
}
```

---

## Example: Cybersecurity CTF Project

```json
{
  "title": "Linux Security Fundamentals",
  "description": "Learn Linux security through hands-on challenges",
  "workspace_type": "cybersecurity",
  "narrative_context": "You've been hired as a junior security analyst. Your first task is to assess a Linux server for vulnerabilities.",
  "learning_objectives": [
    {"level": "apply", "description": "Navigate Linux file systems using command line"},
    {"level": "analyze", "description": "Identify security misconfigurations"}
  ],
  "epics": [
    {
      "title": "Linux Navigation",
      "description": "Master the command line",
      "tasks": [
        {
          "title": "Explore the File System",
          "description": "Learn to navigate directories and find files",
          "subtasks": [
            {
              "title": "Find hidden files",
              "description": "Locate hidden files in the home directory",
              "acceptance_criteria": "- Find all hidden files\n- Identify the flag file",
              "validation": {
                "type": "flag_capture",
                "expected": {
                  "flag": "FLAG{h1dd3n_f1l3s_f0und}"
                }
              },
              "tutor_guidance": {
                "teaching_approach": "Guide through discovery without revealing location",
                "hints_to_give": [
                  "Hidden files in Linux start with a dot (.)",
                  "Try 'ls -la' to see all files including hidden ones",
                  "The flag is somewhere in your home directory"
                ],
                "common_mistakes": [
                  "Using 'ls' without the -a flag",
                  "Not checking subdirectories"
                ]
              }
            }
          ]
        }
      ]
    }
  ]
}
```

---

## Bloom's Taxonomy Levels

Use these for `learning_objectives.level`:

| Level | Description | Example Verbs |
|-------|-------------|---------------|
| `remember` | Recall facts | Define, list, name, recall |
| `understand` | Explain concepts | Describe, explain, summarize |
| `apply` | Use knowledge | Implement, execute, use |
| `analyze` | Break down | Compare, contrast, examine |
| `evaluate` | Judge, assess | Critique, assess, evaluate |
| `create` | Build something new | Design, construct, develop |

---

## File Naming Convention

```
content/projects/
├── DA/                          # Data Analytics
│   └── MN_Part1/               # Maji Ndogo Part 1
├── PYTHON/                      # Python Programming
│   ├── fundamentals/           # Basics course
│   └── data_analysis/          # Data analysis course
└── CYBER/                       # Cybersecurity
    ├── linux_security/         # Linux security basics
    └── network_forensics/      # Network analysis
```

---

## Ingestion Command

```bash
# Validate first (dry run)
python -m ltt.cli.main ingest project path/to/project.json --dry-run

# Then ingest
python -m ltt.cli.main ingest project path/to/project.json
```

---

## Subagent Instructions

When creating project content:

1. **Follow the schema exactly** - Invalid JSON will fail ingestion
2. **Be specific in acceptance_criteria** - Used for validation
3. **Write helpful tutor_guidance** - This is what makes the AI effective
4. **Order subtasks logically** - Dependencies are implicit (earlier = prerequisite)
5. **Include validation configs** - Required for auto-grading
6. **Test with dry-run** - Catches errors before ingestion

---

*See [WORKSPACE_EXTENSIONS.md](./WORKSPACE_EXTENSIONS.md) for full technical specification.*
