# Todo Application Demo (MVP)

A full-featured todo application built with Serv showcasing CRUD operations, local persistence, filtering, and modern web app patterns.

## Features

- Full CRUD operations for todos
- Local JSON file persistence
- Task filtering and search
- Priority levels and categories
- Due dates and reminders
- Responsive single-page interface

## MVP TODO List

### Core Todo Operations
- [ ] Create todo model with validation
- [ ] Implement JSON file storage for persistence
- [ ] Add CRUD API endpoints (create, read, update, delete)
- [ ] Create todo list management logic
- [ ] Add todo completion tracking

### Todo Features
- [ ] Todo title and description
- [ ] Priority levels (high, medium, low)
- [ ] Due dates with date picker
- [ ] Categories/tags for organization
- [ ] Completion status tracking
- [ ] Creation and modification timestamps

### User Interface
- [ ] Single-page todo application
- [ ] Add new todo form
- [ ] Todo list display with checkboxes
- [ ] Inline editing for todos
- [ ] Drag-and-drop reordering
- [ ] Responsive design for mobile

### Filtering and Search
- [ ] Filter by completion status
- [ ] Filter by priority level
- [ ] Filter by category/tag
- [ ] Search by title/description
- [ ] Sort by due date, priority, creation date

### API Endpoints
- [ ] GET /api/todos - List todos with filtering
- [ ] POST /api/todos - Create new todo
- [ ] GET /api/todos/{id} - Get specific todo
- [ ] PUT /api/todos/{id} - Update todo
- [ ] DELETE /api/todos/{id} - Delete todo
- [ ] PATCH /api/todos/{id}/complete - Toggle completion

### Data Persistence
- [ ] JSON file storage (todos.json)
- [ ] Automatic backup on changes
- [ ] Data validation and error handling
- [ ] Sample data generation for demo
- [ ] Import/export functionality

### Extensions Integration
- [ ] Create TodoAppExtension
- [ ] Add data persistence middleware
- [ ] Create API response formatting middleware

## Running the Demo

```bash
cd demos/todo_app
pip install -r requirements.txt  # No extra dependencies needed
serv launch
```

Visit http://localhost:8000 to start managing your todos!

## File Structure

```
demos/todo_app/
├── README.md
├── requirements.txt              # No extra deps needed
├── serv.config.yaml             # Basic config
├── data/
│   └── todos.json               # Local data storage
├── extensions/
│   └── todo_app_extension.py    # Todo API and routes
├── models/
│   └── todo.py                  # Todo data model
├── templates/
│   └── todo_app.html           # Single-page application
└── static/
    ├── todo_app.js             # Frontend JavaScript
    ├── style.css               # Application styling
    └── icons/                  # Todo status icons
```

## MVP Scope

- **Local JSON storage** (no database required)
- **Single-page application** (no complex routing)
- **Basic features** (CRUD + filtering + categories)
- **No user accounts** (single shared todo list)
- **Minimal dependencies** (just Serv + standard library)

## Todo Data Model

```json
{
  "id": "uuid",
  "title": "Buy groceries",
  "description": "Milk, bread, eggs",
  "completed": false,
  "priority": "medium",
  "category": "personal",
  "due_date": "2024-01-15",
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:00:00Z"
}
```

## App Features

### Todo Management
- Add new todos with title, description, priority
- Mark todos as complete/incomplete
- Edit todos inline
- Delete todos with confirmation
- Bulk operations (mark all complete, delete completed)

### Organization
- Priority levels with color coding
- Categories for grouping todos
- Due date tracking with overdue indicators
- Search functionality across title and description

### User Experience
- Keyboard shortcuts for quick actions
- Auto-save on edits
- Undo/redo functionality
- Progress tracking (completed vs total)
- Dark/light mode toggle

## Demo Data

The application starts with sample todos:
- Mix of completed and pending tasks
- Various priorities and categories
- Some with due dates (including overdue)
- Realistic todo content for demonstration

This MVP demonstrates Serv's capabilities for building modern web applications! 