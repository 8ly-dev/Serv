# API Gateway Demo (MVP)

A simple API gateway built with Serv showcasing request routing, API aggregation, and service proxy patterns with local mock services.

## Features

- Request routing to multiple backend services
- API response aggregation
- Request/response transformation
- Basic load balancing
- Service health monitoring
- Request logging and analytics

## MVP TODO List

### Core Gateway Functionality
- [ ] Create request routing logic
- [ ] Implement service proxy functionality
- [ ] Add request/response transformation
- [ ] Create service discovery (in-memory registry)
- [ ] Add basic load balancing (round-robin)
- [ ] Handle service failures gracefully

### Mock Backend Services
- [ ] Users service mock (port 8001)
- [ ] Products service mock (port 8002)
- [ ] Orders service mock (port 8003)
- [ ] Notifications service mock (port 8004)
- [ ] All services with health endpoints

### Request Routing
- [ ] Path-based routing (/api/users/* → users service)
- [ ] Host-based routing (if needed)
- [ ] Request method routing
- [ ] Query parameter routing
- [ ] Header-based routing

### API Aggregation
- [ ] Combine responses from multiple services
- [ ] Create composite endpoints
- [ ] Handle partial failures
- [ ] Response caching for aggregated data
- [ ] Parallel service calls

### Service Management
- [ ] Service registry (in-memory)
- [ ] Health check monitoring
- [ ] Service status tracking
- [ ] Automatic service discovery
- [ ] Service configuration management

### Extensions Integration
- [ ] Create APIGatewayExtension
- [ ] Add routing middleware
- [ ] Create proxy middleware
- [ ] Add logging middleware

## Running the Demo

```bash
cd demos/api_gateway
pip install -r requirements.txt  # aiohttp for HTTP client
# Start the gateway
serv launch

# Start mock services (in separate terminals)
python mock_services/users_service.py     # Port 8001
python mock_services/products_service.py  # Port 8002
python mock_services/orders_service.py    # Port 8003
python mock_services/notifications_service.py # Port 8004
```

Visit http://localhost:8000 to access the gateway dashboard!

## File Structure

```
demos/api_gateway/
├── README.md
├── requirements.txt              # aiohttp for HTTP client
├── serv.config.yaml             # Gateway configuration
├── extensions/
│   ├── api_gateway_extension.py # Main gateway logic
│   ├── routing_extension.py     # Request routing
│   └── monitoring_extension.py  # Service monitoring
├── mock_services/
│   ├── users_service.py         # Mock users API
│   ├── products_service.py      # Mock products API
│   ├── orders_service.py        # Mock orders API
│   └── notifications_service.py # Mock notifications API
├── templates/
│   ├── gateway_dashboard.html   # Gateway management UI
│   └── service_status.html      # Service health status
└── static/
    ├── gateway.js               # Gateway dashboard JS
    └── style.css                # Dashboard styling
```

## MVP Scope

- **Local mock services** (simple HTTP servers)
- **In-memory service registry** (no external discovery)
- **Basic routing** (path-based, no complex rules)
- **Simple load balancing** (round-robin only)
- **No authentication** (public gateway for demo)

## Gateway Routes

### Service Proxying
- `/api/users/*` → Users Service (port 8001)
- `/api/products/*` → Products Service (port 8002)
- `/api/orders/*` → Orders Service (port 8003)
- `/api/notifications/*` → Notifications Service (port 8004)

### Gateway Management
- `/gateway/services` - List registered services
- `/gateway/health` - Aggregated health status
- `/gateway/stats` - Request statistics
- `/gateway/routes` - Show routing configuration

### Aggregated Endpoints
- `/api/user-dashboard/{id}` - Combine user + orders + notifications
- `/api/product-details/{id}` - Product + reviews + related products
- `/api/order-summary/{id}` - Order + items + user + status

## Mock Services

### Users Service (Port 8001)
```python
# GET /users, GET /users/{id}, POST /users
# Sample endpoints with user data
```

### Products Service (Port 8002)
```python
# GET /products, GET /products/{id}, GET /categories
# Sample endpoints with product catalog
```

### Orders Service (Port 8003)
```python
# GET /orders, GET /orders/{id}, POST /orders
# Sample endpoints with order data
```

### Notifications Service (Port 8004)
```python
# GET /notifications/{user_id}, POST /notifications
# Sample endpoints with notification data
```

## Gateway Features

### Request Routing
- Automatic service discovery
- Health-based routing
- Load balancing between service instances
- Fallback handling for service failures

### Response Aggregation
- Combine data from multiple services
- Handle partial failures gracefully
- Cache aggregated responses
- Transform response formats

### Monitoring
- Request/response logging
- Service health monitoring
- Performance metrics tracking
- Error rate monitoring

## Demo Scenarios

1. **Service Proxying**: Route requests to appropriate backend services
2. **Load Balancing**: Distribute requests across multiple service instances
3. **Health Monitoring**: Show service status and handle failures
4. **API Aggregation**: Combine responses from multiple services
5. **Request Transformation**: Modify requests/responses as they pass through

This MVP demonstrates Serv's capabilities for building API gateways and service orchestration! 