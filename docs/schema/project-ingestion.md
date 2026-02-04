# Project Schema for LLM-Based Ingestion

> **Purpose**: This guide explains how to structure learning projects for the Learning Task Tracker system. It's designed to help LLMs convert unstructured learning content into structured, pedagogically-aware project hierarchies.

## Core Principle: Context at Every Level

**At any point in the hierarchy, a learner should have enough context to:**
1. Understand the **big picture** (what am I building overall?)
2. Understand the **current scope** (what am I working on right now?)
3. Know the **learning goals** (what will I learn from this?)
4. See the **success criteria** (how do I know I'm done?)

This is achieved by providing **broad context** at higher levels (project, epic) and **specific, actionable guidance** at lower levels (task, subtask).

---

## Hierarchical Structure

```
Project (Big Picture - "Build an E-commerce Site")
  │
  ├── Epic (Major Feature - "Backend API")
  │   │
  │   ├── Task (Cohesive Unit - "User Authentication")
  │   │   │
  │   │   ├── Subtask (Atomic Work - "Implement JWT token generation")
  │   │   ├── Subtask (Atomic Work - "Create login endpoint")
  │   │   └── Subtask (Atomic Work - "Add password hashing")
  │   │
  │   └── Task ("Product Catalog")
  │       └── Subtask...
  │
  └── Epic ("Frontend UI")
      └── Task...
```

###  Why This Structure?

| Level | Purpose | Context Provided |
|-------|---------|------------------|
| **Project** | Overall learning journey | What you're building, why it matters, overarching skills |
| **Epic** | Major milestone or feature area | High-level architecture, design patterns, key concepts |
| **Task** | Cohesive unit of work | Specific feature/component, how it fits in the epic |
| **Subtask** | Atomic, verifiable work item | Precise implementation details, testable outcome |

---

## JSON Schema Structure

### Project (Root Level)

```json
{
  "title": "Build an E-commerce Website",

  "description": "Build a full-stack e-commerce platform with product catalog, shopping cart, checkout, and admin panel. Uses FastAPI for the backend and React for the frontend. This project teaches full-stack development, database design, authentication, and deployment.",

  "learning_objectives": [
    {"level": "create", "description": "Build a complete full-stack web application"},
    {"level": "apply", "description": "Apply REST API design principles"},
    {"level": "analyze", "description": "Analyze and optimize database queries"}
  ],

  "content": "## Project Overview\n\nYou'll build a complete e-commerce platform from scratch...\n\n### Technologies\n- Backend: FastAPI, PostgreSQL, SQLAlchemy\n- Frontend: React, TypeScript\n- Deployment: Docker, Railway",

  "epics": [...]
}
```

#### Field Explanations

**`title`** *(required)*
- **What**: Short, action-oriented project name
- **Why**: Immediately tells learner what they're building
- **Example**: "Build an E-commerce Website" (not "E-commerce Project")

**`description`** *(recommended)*
- **What**: 2-4 paragraph overview of the entire project
- **Why**: Provides the "big picture" context that learners can reference at any point
- **Include**:
  - What you're building and why
  - Key technologies and tools
  - How components fit together
  - What makes this project valuable
- **Example**: "Build a full-stack e-commerce platform... This project teaches..."

**`learning_objectives`** *(recommended)*
- **What**: Array of learning goals using Bloom's Taxonomy
- **Why**: Tells learners what skills they'll gain from completing the project
- **Bloom Levels**: `remember`, `understand`, `apply`, `analyze`, `evaluate`, `create`
- **Rule**: Project-level objectives should be high-level (usually `create`, `evaluate`, `analyze`)
- **Example**: `{"level": "create", "description": "Build a complete full-stack application"}`

**`content`** *(optional)*
- **What**: Markdown-formatted learning materials, architecture diagrams, setup instructions
- **Why**: Provides reference material learners can consult when stuck
- **Include**:
  - Architecture overview
  - Technology stack explanations
  - Setup/installation instructions
  - Design decisions and rationale
- **When to use**: Large-scale explanatory content that applies to the whole project

**`narrative_context`** *(optional - Project level only)*
- **What**: Real-world story or context that makes the project meaningful
- **Why**: Motivates learners by connecting abstract technical work to real impact
- **Include**:
  - Who benefits from this work
  - Real-world scenario or problem being solved
  - Stakes or consequences
  - Human element (people, communities, organizations)
- **Example**: "This data comes from President Naledi's water quality initiative. You are helping analyze survey data that will impact real communities in rural areas. The government will use your analysis to determine where to install new water purification systems."
- **Tone**: Engaging, human-centered, makes learner feel like their work matters
- **Length**: 2-4 sentences typically
- **When to use**: Projects where real-world context enhances motivation and understanding

**`epics`** *(array)*
- **What**: Major feature areas or milestones
- **Why**: Breaks large projects into manageable phases
- **Example**: "Build Backend API", "Build Frontend UI", "Add Payment Processing"

---

### Epic (Major Feature Level)

```json
{
  "title": "Build FastAPI Backend",

  "description": "Create a complete REST API backend with user authentication, product catalog, shopping cart, and order management. Uses PostgreSQL for data storage and SQLAlchemy for ORM. Implements JWT-based authentication and role-based access control.",

  "learning_objectives": [
    {"level": "apply", "description": "Build REST APIs with FastAPI"},
    {"level": "apply", "description": "Design normalized database schemas"},
    {"level": "understand", "description": "Understand JWT authentication flow"}
  ],

  "content": "## Backend Architecture\n\nThe API follows a layered architecture:\n- Routes (endpoints)\n- Services (business logic)\n- Models (database)\n\n### Key Patterns\n- Dependency injection for database sessions\n- Async/await for all database operations\n- Pydantic for request/response validation",

  "tasks": [...]
}
```

#### Epic Field Guidance

**`description`** *(recommended)*
- **Scope**: This epic's feature area (not the whole project)
- **Include**:
  - What features/components are included
  - How they relate to each other
  - Key architectural patterns
  - Database/API design overview
- **Example**: "Create a complete REST API backend with user authentication..."

**`learning_objectives`** *(recommended)*
- **Scope**: Skills learned from completing this epic
- **Bloom Level**: Usually `apply`, `understand`, `analyze` (more specific than project-level)
- **Example**: `{"level": "apply", "description": "Build REST APIs with FastAPI"}`

**`content`** *(optional)*
- **Scope**: Architecture, patterns, and concepts for this feature area
- **Include**:
  - Component diagrams
  - API design patterns
  - Database schema explanation
  - Code organization
- **Example**: "## Backend Architecture\n\nThe API follows a layered architecture..."

**`tasks`** *(array)*
- **What**: Cohesive units of work within this epic
- **Example**: "User Authentication", "Product Catalog", "Shopping Cart"

---

### Task (Cohesive Unit Level)

```json
{
  "title": "Implement User Authentication",

  "description": "Build complete user authentication system with registration, login, JWT token generation, and protected routes. Includes password hashing with bcrypt, token refresh, and email validation.",

  "acceptance_criteria": "- Users can register with email/password\n- Login returns a valid JWT token\n- Protected routes verify tokens\n- Passwords are hashed with bcrypt\n- All tests pass",

  "learning_objectives": [
    {"level": "apply", "description": "Implement JWT authentication in FastAPI"},
    {"level": "understand", "description": "Understand password hashing with bcrypt"},
    {"level": "remember", "description": "Recall HTTP authentication headers"}
  ],

  "priority": 0,

  "content": "## Authentication Flow\n\n1. User submits email/password to /auth/register\n2. Server hashes password with bcrypt\n3. User record saved to database\n4. Login endpoint generates JWT token\n5. Client includes token in Authorization header\n\n### Key Concepts\n- JWT (JSON Web Tokens): Stateless authentication\n- bcrypt: One-way password hashing\n- Bearer tokens: HTTP authorization standard",

  "dependencies": [],

  "subtasks": [...]
}
```

#### Task Field Guidance

**`title`** *(required)*
- **What**: Specific feature or component you're implementing
- **Action-oriented**: "Implement User Authentication" (not "Authentication")
- **Scope**: Should be completable in a reasonable timeframe

**`description`** *(recommended)*
- **Scope**: This specific feature/component
- **Include**:
  - What you're building
  - Key components included
  - How it integrates with other parts
- **Length**: 2-3 sentences to 1 paragraph
- **Example**: "Build complete user authentication system with registration, login..."

**`acceptance_criteria`** *(recommended - critical for subtasks)*
- **What**: Specific, testable requirements for completion
- **Format**: Bullet list (markdown)
- **Each criterion should be**:
  - Specific and measurable
  - Testable (can verify yes/no)
  - Outcome-focused (not process-focused)
- **Example**:
  ```
  - Users can register with email/password
  - Login returns a valid JWT token
  - Protected routes verify tokens
  - All tests pass
  ```
- **Why**: This is how validation determines if work is complete

**`learning_objectives`** *(recommended)*
- **Scope**: What learner will know/be able to do after this task
- **Bloom Levels**: Mix of `apply` (implementation), `understand` (concepts), `remember` (facts)
- **Example**: `{"level": "apply", "description": "Implement JWT authentication in FastAPI"}`

**`priority`** *(optional, default: 2)*
- **Scale**: 0 (critical) to 4 (nice-to-have)
- **Use P0 for**: Foundational tasks that block everything else
- **Example**: "Set up project structure" = P0

**`content`** *(optional)*
- **Scope**: Explanations, examples, and guidance for this specific task
- **Include**:
  - Step-by-step flow/process
  - Key concepts explained
  - Code examples
  - Common pitfalls
- **Length**: Can be substantial (multiple paragraphs/code blocks)
- **Why**: Gives learner reference material without leaving the task
- **Example**: "## Authentication Flow\n\n1. User submits... 2. Server hashes..."

**`dependencies`** *(array of title strings)*
- **What**: Other tasks that must be completed first
- **Format**: Array of task/subtask titles from the same project
- **Resolution**: Titles are matched to IDs during ingestion
- **Example**: `["Set up project structure", "Create database models"]`
- **Why**: Enforces logical ordering and prevents learners from getting stuck

**`subtasks`** *(array)*
- **What**: Atomic, independently completable pieces of work
- **When to use**: Break task into 3-8 subtasks if it's complex
- **Example**: Authentication task broken into "JWT generation", "Login endpoint", "Password hashing"

---

### Subtask (Atomic Work Level)

```json
{
  "title": "Create JWT token generation function",

  "description": "Implement a function that generates JWT tokens with user ID and expiration. Token should expire after 24 hours and include user_id in the payload. Use python-jose library.",

  "acceptance_criteria": "- Function accepts user_id and returns JWT string\n- Token includes user_id in payload\n- Token expires after 24 hours\n- Uses HS256 algorithm\n- Secret key from environment variable\n- Tests verify token can be decoded",

  "learning_objectives": [
    {"level": "apply", "description": "Create JWT tokens using python-jose"},
    {"level": "understand", "description": "Understand JWT structure (header, payload, signature)"}
  ],

  "priority": 0,

  "content": "## JWT Token Structure\n\nJWTs have three parts:\n1. Header: Algorithm and token type\n2. Payload: User data (user_id, exp)\n3. Signature: Verification hash\n\n### Implementation\n```python\nfrom jose import jwt\nfrom datetime import datetime, timedelta\n\ndef create_token(user_id: str) -> str:\n    payload = {\n        \"user_id\": user_id,\n        \"exp\": datetime.utcnow() + timedelta(days=1)\n    }\n    return jwt.encode(payload, SECRET_KEY, algorithm=\"HS256\")\n```\n\n### Testing\nVerify the token can be decoded and contains correct user_id."
}
```

#### Subtask Field Guidance

**`title`** *(required)*
- **What**: Single, atomic piece of work
- **Action**: Starts with verb ("Create", "Implement", "Add", "Write", "Discuss", "Consider", "Reflect")
- **Scope**: Should take 15-90 minutes typically
- **Example**: "Create JWT token generation function"

**`subtask_type`** *(optional, default: "exercise")*
- **What**: Distinguishes between conversational/discussion subtasks and technical work
- **Values**:
  - `"exercise"` (default) - Technical work requiring code/output, needs acceptance criteria
  - `"conversational"` - Discussion, reflection, or context-setting, no validation needed
- **Why**: Allows explicit Socratic moments in the learning path that are tracked but not tested
- **Behavior by type**:
  - **`exercise`**: Requires `acceptance_criteria`, tutor validates work, blocks progress until complete
  - **`conversational`**: No `acceptance_criteria` needed, tutor engages in discussion, learner proceeds after engagement
- **Example conversational subtask**:
  ```json
  {
    "title": "Consider the human impact of long queue times",
    "subtask_type": "conversational",
    "description": "Before we write queries to find long queue times, let's think about what this data represents.",
    "content": "Imagine waiting over 8 hours just to collect water for your family. What activities would you miss? How would this affect children's education? Working parents?",
    "learning_objectives": [
      {"level": "evaluate", "description": "Evaluate the real-world significance of water access data"}
    ]
  }
  ```
- **Typical pattern**: Conversational subtasks often precede technical ones, with dependencies ensuring the discussion happens first:
  ```
  Task: Analyze Queue Times
    ├── Subtask: "Consider the human impact" (conversational)
    └── Subtask: "Write WHERE clause for long queues" (exercise, depends on above)
  ```

**`description`** *(critical)*
- **What**: Precise specification of what to build
- **Include**:
  - Exactly what to create
  - Key requirements/constraints
  - Libraries/tools to use
- **Length**: 2-4 sentences
- **Why**: This is what the LLM tutor uses to guide implementation
- **Example**: "Implement a function that generates JWT tokens with user ID and expiration. Token should expire after 24 hours..."

**`acceptance_criteria`** *(required for `exercise` subtasks, omit for `conversational`)*
- **What**: Specific, testable requirements
- **Format**: Bullet list in markdown
- **Each criterion**:
  - Must be verifiable (can be tested)
  - Should be specific (not "works correctly")
  - Include edge cases
- **Why**: This is used to validate submissions and determine if subtask can be closed
- **Note**: For `conversational` subtasks, omit this field entirely - the tutor manages progression based on engagement, not validation
- **Example**:
  ```
  - Function accepts user_id and returns JWT string
  - Token includes user_id in payload
  - Token expires after 24 hours
  - Tests verify token can be decoded
  ```

**`learning_objectives`** *(recommended)*
- **Scope**: Specific skills from this subtask
- **Bloom Levels**: Usually `apply` (doing), `understand` (concepts), `remember` (syntax)
- **Specific**: Tied to this exact subtask, not general
- **Example**: `{"level": "apply", "description": "Create JWT tokens using python-jose"}`

**`content`** *(optional but valuable)*
- **What**: Tutorial/guide content specific to this subtask
- **Include**:
  - Concept explanations
  - Code examples
  - Step-by-step guidance
  - Common mistakes/pitfalls
- **Length**: Can be substantial (this is learning material)
- **Why**: LLM tutor can reference this when helping learner
- **Example**: Complete code example with explanations

**`tutor_guidance`** *(optional - Task/Subtask levels)*
- **What**: Strategic guidance for the LLM tutor on HOW to teach this task
- **Why**: Shapes the tutoring approach, discussion style, and intervention strategy
- **Structure** (all fields optional):
  ```json
  {
    "teaching_approach": "Start with real-world context before introducing SQL syntax",
    "discussion_prompts": [
      "What does 500 minutes mean in real life?",
      "Why might we want to filter by time spent?"
    ],
    "common_mistakes": [
      "Using = for pattern matching instead of LIKE",
      "Forgetting the % wildcards in LIKE queries",
      "Not handling NULL values"
    ],
    "hints_to_give": [
      "Try SHOW TABLES first to see what's available",
      "Look at the schema - what column contains time data?",
      "Remember LIKE uses % as a wildcard"
    ],
    "answer_rationale": "This query finds records that SAY clean but ARE dirty - a logical contradiction that indicates data entry errors."
  }
  ```
- **Field Explanations**:
  - **`teaching_approach`**: Overall strategy (e.g., "Start with examples", "Use Socratic questioning")
  - **`discussion_prompts`**: Open-ended questions to provoke thinking
  - **`common_mistakes`**: What learners typically get wrong (helps tutor prevent/address)
  - **`hints_to_give`**: Progressive hints from general to specific
  - **`answer_rationale`**: Explanation of WHY an answer works, not just what it is (helps tutor explain logic)
- **Example Use Cases**:
  - Guide tutors to use real-world examples before abstract concepts
  - Provide Socratic questions for conceptual understanding
  - Warn tutors about common errors to watch for
  - Suggest hint progression (don't give answers immediately)
- **When to use**: Complex subtasks where tutoring strategy matters

**`priority`** *(optional)*
- **Use**: Mark foundational subtasks as P0
- **Example**: "Set up FastAPI app instance" = P0 (everything depends on it)

---

## Bloom's Taxonomy Levels

Learning objectives use Bloom's Taxonomy to categorize cognitive skills:

| Level | Cognitive Skill | When to Use | Example |
|-------|----------------|-------------|---------|
| **`remember`** | Recall facts, syntax, definitions | Basic knowledge, APIs, commands | "Recall FastAPI route decorator syntax" |
| **`understand`** | Explain concepts, interpret | Understanding how/why things work | "Understand how JWT tokens prevent tampering" |
| **`apply`** | Use knowledge to solve problems | Implementation, coding | "Implement JWT authentication in FastAPI" |
| **`analyze`** | Break down and examine | Debugging, architecture review | "Analyze database query performance" |
| **`evaluate`** | Judge, critique, compare | Design decisions, trade-offs | "Evaluate different authentication strategies" |
| **`create`** | Build something new | Projects, complex features | "Build a complete authentication system" |

### Objective Placement Guidelines

- **Project level**: `create`, `evaluate` (high-level synthesis)
- **Epic level**: `apply`, `analyze` (feature-level skills)
- **Task level**: `apply`, `understand` (component-level skills)
- **Subtask level**: `apply`, `understand`, `remember` (specific implementation skills)

**Example Progression**:
```
Project: "Create a full-stack web application"  (create)
  Epic: "Apply REST API design principles"      (apply)
    Task: "Implement user authentication"       (apply)
      Subtask: "Understand JWT token structure" (understand)
      Subtask: "Apply python-jose library"      (apply)
```

---

## Context Distribution: The Key Insight

**The learner should never need to "zoom out" to understand what they're doing.**

At each level, provide:

### 1. Broad Context (from parents)
- Inherited from project → epic → task hierarchy
- Answers: "Why am I doing this?"
- Provided through hierarchy traversal

### 2. Specific Context (at this level)
- Defined in `description`, `content`, `learning_objectives`
- Answers: "What exactly should I build?"
- Provided in the task itself

### 3. Success Criteria (clear finish line)
- Defined in `acceptance_criteria`
- Answers: "How do I know I'm done?"
- Used for validation

### Example: Full Context Stack

When a learner is working on subtask "Create JWT token generation function":

**Broad Context (from hierarchy)**:
- Project: "Building an e-commerce site" → Why this matters
- Epic: "Backend API" → Where this fits
- Task: "User Authentication" → What feature this belongs to

**Specific Context (at subtask level)**:
- Description: "Implement a function that generates JWT tokens..."
- Learning Objectives: "Apply python-jose library to create JWT tokens"
- Content: Code examples, JWT structure explanation
- Acceptance Criteria: "Function accepts user_id and returns JWT string..."

**At no point should the learner think "I don't understand why I'm doing this" or "I don't know what to build."**

---

## Field-by-Field Schema

### Complete Field Reference

```json
{
  // ==================== PROJECT ====================
  "title": "string (required)",
  // Short, action-oriented project name
  // Example: "Build an E-commerce Website"

  "description": "string (recommended)",
  // 2-4 paragraphs: what you're building, why, how components fit
  // Include: technologies, goals, value proposition

  "learning_objectives": [
    {
      "level": "remember|understand|apply|analyze|evaluate|create",
      "description": "string - what skill is learned"
    }
  ],
  // Project-level: high-level skills (create, evaluate, analyze)
  // Should be 2-5 objectives

  "content": "string (markdown, optional)",
  // Long-form learning materials: architecture, setup, patterns
  // Can include diagrams, code examples, explanations

  "narrative_context": "string (optional)",
  // Real-world story or context that makes the project meaningful
  // Example: "This data comes from President Naledi's water quality initiative..."
  // Makes learners feel their work has real impact

  "epics": [
    {
      // ==================== EPIC ====================
      "title": "string (required)",
      // Major feature area
      // Example: "Build FastAPI Backend"

      "description": "string (recommended)",
      // This epic's scope: features included, architecture
      // 1-2 paragraphs

      "learning_objectives": [
        {
          "level": "apply|analyze|understand",
          "description": "Epic-level skills"
        }
      ],
      // Skills from completing this feature area

      "content": "string (optional)",
      // Feature-level architecture, patterns, design decisions

      "tasks": [
        {
          // ==================== TASK ====================
          "title": "string (required)",
          // Specific feature/component
          // Example: "Implement User Authentication"

          "description": "string (recommended)",
          // What you're building in this task, how it fits
          // 2-4 sentences

          "acceptance_criteria": "string (recommended)",
          // Bullet list of testable requirements
          // Format: "- Requirement 1\n- Requirement 2"

          "learning_objectives": [
            {
              "level": "apply|understand",
              "description": "Task-level skills"
            }
          ],
          // Skills from this component

          "priority": 0-4,  // Optional, default 2
          // 0 = critical foundation, 4 = nice-to-have

          "content": "string (optional)",
          // Implementation guidance, examples, patterns

          "tutor_guidance": {
            "teaching_approach": "string (optional)",
            "discussion_prompts": ["string"],
            "common_mistakes": ["string"],
            "hints_to_give": ["string"]
          },
          // Strategic guidance for LLM tutor on HOW to teach this

          "dependencies": ["Task Title", "Other Task"],
          // Array of task titles this depends on
          // Resolved to IDs during ingestion

          "subtasks": [
            {
              // ==================== SUBTASK ====================
              "title": "string (required)",
              // Atomic piece of work
              // Example: "Create JWT token generation function"

              "description": "string (critical)",
              // Precise specification: what to build, how, with what
              // 2-4 sentences with details

              "acceptance_criteria": "string (critical)",
              // Specific, testable requirements
              // Used for validation

              "learning_objectives": [
                {
                  "level": "apply|understand|remember",
                  "description": "Specific skill"
                }
              ],
              // Very specific to this implementation

              "content": "string (valuable)",
              // Tutorial content: examples, explanations, guidance
              // This is where you teach HOW to do it

              "tutor_guidance": {
                "teaching_approach": "string (optional)",
                "discussion_prompts": ["string"],
                "common_mistakes": ["string"],
                "hints_to_give": ["string"]
              },
              // Strategic tutoring guidance for this subtask

              "priority": 0-4,
              // Mark P0 for foundational subtasks

              "subtasks": []
              // Can nest subtasks infinitely for complex work
            }
          ]
        }
      ]
    }
  ]
}
```

---

## Practical Guidelines for LLM-Based Conversion

### When Converting Unstructured Content to Projects

1. **Identify the Overall Goal**
   - What is the learner building?
   - This becomes the **project title**
   - Project description explains why and how

2. **Break Into Feature Areas**
   - Major milestones or system components
   - These become **epics**
   - Usually 2-5 epics per project

3. **Identify Cohesive Work Units**
   - Each epic has 3-8 **tasks**
   - Each task should be a complete feature/component
   - Tasks should be dependency-aware

4. **Break Into Atomic Steps**
   - Complex tasks get **subtasks**
   - Each subtask is one specific thing to implement
   - Subtasks must have clear acceptance criteria

5. **Add Learning Objectives at All Levels**
   - Project: What skills gained overall?
   - Epic: What domain knowledge?
   - Task: What implementation skills?
   - Subtask: What specific techniques?

6. **Distribute Context Appropriately**
   - **Project/Epic**: Architecture, broad patterns, "why"
   - **Task**: Feature specifics, integration points
   - **Subtask**: Implementation details, code examples, "how"

### Example: Converting a Tutorial

**Unstructured Input**:
> "Learn FastAPI by building a todo list API. First set up FastAPI and create a simple hello world endpoint. Then create a database with SQLAlchemy. Add CRUD endpoints for todos. Finally, add user authentication with JWT tokens."

**Structured Output**:
```json
{
  "title": "Build a Todo List API",
  "description": "Build a complete REST API for managing todo lists using FastAPI and PostgreSQL. Learn API design, database integration, and authentication.",
  "learning_objectives": [
    {"level": "create", "description": "Build a complete REST API"},
    {"level": "apply", "description": "Apply REST principles"}
  ],
  "epics": [
    {
      "title": "API Foundation",
      "tasks": [
        {
          "title": "Set up FastAPI Project",
          "priority": 0,
          "subtasks": [
            {"title": "Create FastAPI app instance"},
            {"title": "Create hello world endpoint"}
          ]
        },
        {
          "title": "Set up Database",
          "dependencies": ["Set up FastAPI Project"],
          "subtasks": [
            {"title": "Configure SQLAlchemy connection"},
            {"title": "Create Todo model"}
          ]
        }
      ]
    },
    {
      "title": "Todo Management",
      "tasks": [
        {
          "title": "Implement CRUD Endpoints",
          "dependencies": ["Set up Database"],
          "subtasks": [
            {"title": "Create GET /todos endpoint"},
            {"title": "Create POST /todos endpoint"},
            {"title": "Create PUT /todos/{id} endpoint"},
            {"title": "Create DELETE /todos/{id} endpoint"}
          ]
        }
      ]
    },
    {
      "title": "Authentication",
      "tasks": [
        {
          "title": "Add JWT Authentication",
          "dependencies": ["Implement CRUD Endpoints"],
          "subtasks": [
            {"title": "Create user registration endpoint"},
            {"title": "Create login endpoint with JWT"},
            {"title": "Add authentication middleware"}
          ]
        }
      ]
    }
  ]
}
```

---

## Minimal vs. Complete Projects

### Minimal Project (Quick Start)

```json
{
  "title": "Build Todo API",
  "epics": [
    {
      "title": "Core Features",
      "tasks": [
        {"title": "Set up FastAPI"},
        {"title": "Create CRUD endpoints"}
      ]
    }
  ]
}
```
- **Use when**: Simple projects, rapid prototyping
- **Missing**: Descriptions, objectives, acceptance criteria
- **Trade-off**: Less guidance for learners

### Complete Project (Recommended)

```json
{
  "title": "Build Todo API",
  "description": "Full description...",
  "learning_objectives": [...],
  "content": "## Overview...",
  "epics": [
    {
      "title": "Core Features",
      "description": "...",
      "learning_objectives": [...],
      "tasks": [
        {
          "title": "Set up FastAPI",
          "description": "...",
          "acceptance_criteria": "- App runs\n- Health endpoint works",
          "learning_objectives": [...],
          "content": "## FastAPI Basics...",
          "subtasks": [
            {
              "title": "Create app instance",
              "description": "...",
              "acceptance_criteria": "...",
              "content": "```python\nfrom fastapi import FastAPI..."
            }
          ]
        }
      ]
    }
  ]
}
```
- **Use when**: Production learning projects
- **Benefits**: Rich guidance, clear objectives, testable outcomes

---

## Special Considerations

### Acceptance Criteria Best Practices

✅ **Good Criteria** (specific, testable):
- "Function returns a valid JWT token"
- "Endpoint returns 401 for invalid credentials"
- "Password is hashed before storing"
- "All unit tests pass"

❌ **Poor Criteria** (vague, subjective):
- "Code works correctly"
- "Follows best practices"
- "Is well-written"

### Content Field Usage

**When to use `content` vs. external materials**:

- **Use `content` field** when:
  - Material is specific to this task/subtask
  - Code examples are short (<50 lines)
  - Explanations are focused (1-3 concepts)
  - Learner needs immediate reference

- **Use external `content_refs`** when:
  - Material is reusable across tasks
  - Documentation is extensive (full tutorials)
  - External resources (videos, articles)

**Markdown Support**: The `content` field supports full markdown including:
- Headers, lists, code blocks
- Links to external resources
- Inline code
- Tables for comparisons

### Dependency Resolution

Dependencies use **title strings**, not IDs:

```json
{
  "title": "Create POST endpoint",
  "dependencies": ["Set up database models", "Create GET endpoint"]
}
```

**During ingestion**:
- System builds a title → ID map
- Matches dependency titles to task IDs
- Creates `BLOCKS` type dependencies
- Dependencies must exist in the same project

**Limitation**: If two tasks have the same title, behavior is undefined (use unique titles)

---

## LLM Prompt Guidance

### When Using an LLM to Structure Content

**Prompt Template**:
```
Convert the following learning content into a structured project for the Learning Task Tracker system.

Requirements:
1. Create a project with epics, tasks, and subtasks
2. At each level, provide enough context so a learner knows:
   - Why they're building this (broad context from parents)
   - What exactly to build (specific description at this level)
   - How to know they're done (acceptance criteria)
3. Add learning objectives at each level using Bloom's taxonomy
4. Include tutorial content in the `content` field for subtasks
5. Set dependencies where logical ordering matters
6. Ensure acceptance criteria are specific and testable

Content to convert:
[paste unstructured content here]

Output as JSON matching the schema in SCHEMA-FOR-LLM-INGESTION.md
```

### Quality Checklist for Generated Projects

- [ ] Every subtask has clear `acceptance_criteria`
- [ ] Descriptions get more specific as you go down the hierarchy
- [ ] Learning objectives use appropriate Bloom levels
- [ ] Dependencies reflect logical ordering
- [ ] No subtask is too large (if >90min, break it down further)
- [ ] Content field provides value (not just restating the title)
- [ ] A learner at any subtask can understand what they're building and why

---

## Example: Water Analysis Project

See [water_analysis_project.json](../src/ltt/tempdocs/water_analysis_project.json) for a complete example demonstrating:
- Rich context at all levels
- Bloom's taxonomy usage
- Dependency chains
- Comprehensive acceptance criteria
- Tutorial content in subtasks

---

## Ingestion Command

Once you have a JSON file:

```bash
# Dry run (validate without creating)
ltt ingest project my_project.json --dry-run

# Import for real
ltt ingest project my_project.json

# Export for backup/sharing
ltt project export proj-abc123 --output backup.json
```

---

## Summary: The Mental Model

Think of the project structure as **progressive disclosure of context**:

1. **Project**: The destination ("Build an e-commerce site")
2. **Epic**: The major waypoint ("Backend API complete")
3. **Task**: The immediate goal ("User authentication working")
4. **Subtask**: The current step ("JWT token function implemented")

At each level:
- **What** (description): Gets more specific
- **Why** (objectives): Gets more concrete
- **How** (content): Gets more detailed
- **Done** (criteria): Gets more testable

**The LLM tutor can use this hierarchy to**:
- Provide big-picture reminders (project/epic)
- Explain current feature (task)
- Give step-by-step guidance (subtask)
- Validate work (acceptance criteria)

**All from the database, no external state needed.**
