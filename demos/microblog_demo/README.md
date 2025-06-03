# 🌟 Microblog Demo - Database Integration Showcase

A comprehensive demonstration of **Serv's database integration system** featuring SQLite with Ommi ORM, clean architecture, and modern web development patterns.

## 🎯 What This Demo Shows

### **Database Integration Features:**
✅ **Database Configuration** - YAML-based database setup  
✅ **Ommi ORM Integration** - Modern async ORM with auto-detection  
✅ **Multi-Database Support** - Ready for multiple database instances  
✅ **Dependency Injection** - Clean database access patterns  
✅ **CLI Management** - Database commands and configuration  

### **Framework Features:**
✅ **Extension Architecture** - Modular, reusable components  
✅ **Type-Safe Routes** - Request/response type annotations  
✅ **Clean Separation** - Models, routes, and presentation logic  
✅ **Form Handling** - Automatic form parsing and validation  
✅ **Error Handling** - Graceful error pages and logging  

## 🚀 Quick Start

### **1. Test the Demo**
```bash
cd demos/microblog_demo
uv run python test_demo.py
```

### **2. Run the Application**
```bash
uv run python -m serv launch
```

### **3. Visit the Site**
Open http://localhost:8000 in your browser

## 🏗️ Architecture Overview

### **Database Configuration (`serv.config.yaml`)**
```yaml
databases:
  blog:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "sqlite:///blog.db"
    qualifier: "blog"
```

### **Extension Structure**
```
extensions/microblog/
├── extension.yaml      # Extension metadata and routing
├── microblog.py       # Main extension class  
├── models.py          # Database models (Ommi ORM)
├── routes.py          # Web routes with type safety
└── __init__.py        # Python package
```

## 📊 Database Schema

When Ommi is installed, the demo creates:

```sql
CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    content VARCHAR(5000) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 🛠️ Database CLI Commands

The demo showcases Serv's database CLI:

```bash
# List configured databases
uv run python -m serv database list

# Check database status  
uv run python -m serv database status

# Test database connections
uv run python -m serv database test

# View configuration examples
uv run python -m serv database config

# List available providers
uv run python -m serv database providers
```

## 🔧 Full Database Functionality

For complete database functionality, install Ommi:

```bash
uv add ommi
```

This will enable:
- ✅ **Real database operations** (create, read, update, delete)
- ✅ **Automatic schema creation** on startup  
- ✅ **Type-safe database queries** with Ommi ORM
- ✅ **Connection pooling** and optimization
- ✅ **Database migrations** support

## 📁 Key Files Explained

| File | Purpose | Database Integration |
|------|---------|---------------------|
| `serv.config.yaml` | App configuration | **Database connection settings** |
| `extensions/microblog/extension.yaml` | Extension metadata | Route definitions |
| `extensions/microblog/microblog.py` | Extension lifecycle | **Database startup logic** |
| `extensions/microblog/models.py` | Data models | **Ommi ORM models and schema** |
| `extensions/microblog/routes.py` | Web routes | **Database injection and queries** |
| `test_demo.py` | Demo verification | Configuration validation |

## 💡 Learning Points

### **1. Database Configuration**
- YAML-based configuration with environment variable support
- Multiple database support with qualifiers
- Provider-based architecture for different ORMs

### **2. Dependency Injection**
- Clean separation of database concerns
- Type-safe database access in routes
- Container-managed database lifecycle

### **3. Extension Architecture**
- Self-contained, reusable components  
- YAML-based routing configuration
- Event-driven lifecycle management

### **4. Modern Web Patterns**
- Type-annotated request/response handling
- Automatic form parsing and validation
- Clean HTML templating within Python

## 🎓 Next Steps

1. **Explore the Code** - Study the clean separation of concerns
2. **Install Ommi** - See full database functionality  
3. **Extend the Demo** - Add user authentication, comments, etc.
4. **Create Your Own** - Use this as a template for your projects

## 🔍 Development Mode

Run with enhanced debugging:
```bash
uv run python -m serv --dev launch
```

This enables:
- 🔄 **Auto-reload** on file changes
- 🐛 **Enhanced error reporting** with full tracebacks  
- 📝 **Debug logging** for all components
- ⚡ **Development-optimized** server settings

---

This demo showcases how **Serv's database integration** makes modern web development both powerful and enjoyable! 🚀