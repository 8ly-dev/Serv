# 🎯 Serv Framework Demos

A collection of demonstration applications showcasing different aspects of the Serv web framework.

## 🌟 Featured Demo: Database Integration

### **🗄️ [Microblog Demo](./microblog_demo/)**
**A comprehensive showcase of Serv's database integration system**

**What it demonstrates:**
- ✅ **Complete Database Integration** - YAML config, Ommi ORM, CLI management
- ✅ **Modern Web Architecture** - Type-safe routes, clean separation, DI patterns  
- ✅ **Extension System** - Modular, reusable components
- ✅ **Production Patterns** - Error handling, logging, validation

**Quick start:**
```bash
cd demos/microblog_demo
uv run python validate_demo.py  # Validate setup
uv run python -m serv launch    # Run the app
```

**Key features showcased:**
- Database configuration via YAML
- Ommi ORM integration with auto-detection
- Multi-database support with qualifiers
- CLI database management commands
- Clean dependency injection patterns
- Type-safe route handlers
- Form processing and validation

---

## 📚 Other Demos

### **API & Backend**
- **[API Gateway](./api_gateway/)** - Service composition and routing
- **[Blog API](./blog_api/)** - RESTful API patterns
- **[JSON API Playground](./json_api_playground/)** - API development and testing

### **Real-time Features**  
- **[WebSocket Chat](./websocket_chat/)** - Real-time messaging
- **[Realtime Chat](./realtime_chat/)** - Advanced chat features
- **[SSE Dashboard](./sse_dashboard/)** - Server-sent events

### **Web Applications**
- **[Todo App](./todo_app/)** - Classic CRUD application
- **[Form Wizard](./form_wizard/)** - Multi-step form handling
- **[E-commerce Site](./ecommerce_site/)** - Shopping cart and payments

### **Infrastructure**
- **[File Upload Service](./file_upload_service/)** - File handling and storage
- **[Performance Showcase](./performance_showcase/)** - Optimization techniques
- **[Plugin Middleware Demo](./plugin_middleware_demo/)** - Middleware patterns

---

## 🚀 Getting Started

### **1. Choose a Demo**
Browse the demos above and pick one that interests you.

### **2. Navigate to Demo Directory**
```bash
cd demos/[demo-name]
```

### **3. Run the Demo**
Most demos can be started with:
```bash
uv run python -m serv launch
```

### **4. Explore the Code**
Each demo includes:
- 📖 **Comprehensive README** - Setup and learning guide
- 🏗️ **Clean Architecture** - Well-organized, commented code  
- 🧪 **Working Examples** - Real functionality you can interact with
- 💡 **Learning Points** - Key concepts and patterns highlighted

---

## 💡 Learning Path

### **Beginner**: Start Here
1. **[Todo App](./todo_app/)** - Basic CRUD operations
2. **[Microblog Demo](./microblog_demo/)** - Database integration
3. **[Form Wizard](./form_wizard/)** - Form handling

### **Intermediate**: Expand Your Skills  
1. **[WebSocket Chat](./websocket_chat/)** - Real-time features
2. **[API Gateway](./api_gateway/)** - Service architecture
3. **[File Upload Service](./file_upload_service/)** - File handling

### **Advanced**: Master the Framework
1. **[Performance Showcase](./performance_showcase/)** - Optimization
2. **[Plugin Middleware Demo](./plugin_middleware_demo/)** - Advanced patterns
3. **[E-commerce Site](./ecommerce_site/)** - Production complexity

---

## 🛠️ Development Tips

### **Testing Demos**
```bash
# Validate demo setup
uv run python validate_demo.py  # (if available)

# Run with development mode  
uv run python -m serv --dev launch

# Test configuration
uv run python -m serv config validate
```

### **Database Demos**  
```bash
# Check database setup
uv run python -m serv database list
uv run python -m serv database status

# View configuration examples
uv run python -m serv database config
```

### **Debugging**
- Use `--dev` flag for enhanced error reporting
- Check logs for detailed information
- Use `--dry-run` to validate without starting server

---

## 📖 Documentation

Each demo includes comprehensive documentation covering:

- **🎯 Purpose** - What the demo demonstrates
- **🏗️ Architecture** - How it's structured  
- **🚀 Quick Start** - Get running immediately
- **💡 Key Concepts** - Learning objectives
- **🔧 Customization** - How to extend and modify
- **📚 References** - Related documentation

---

**Explore, learn, and build amazing web applications with Serv! 🌟**